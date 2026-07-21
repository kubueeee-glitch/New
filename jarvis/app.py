"""Orkiestrator Jarvisa — spina E1–E8 w jedną aplikację (asyncio).

Przepływ jednej wypowiedzi:
  pętla głosowa (wątek) → on_utterance → router L0/L1 → ewentualny skill/akcja/wzrok
  → odpowiedź zdaniami → TTS. Wszystko oznajmiane na bus dla HUD-u i pamięci.

Menedżer trybów, watchdog GPU, scheduler i sentinel biegną jako zadania tła.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from .actions import ActionGate
from .actions.handlers import build_handlers
from .audio.loop import VoiceLoop
from .config import JarvisConfig, default_config_path, load_config
from .core.bus import Bus
from .core.scheduler import Scheduler
from .hud.state import HudState
from .llm.cache import DiskCache
from .llm.gpu import GpuWatchdog, make_gaming_detector, read_gpu_stats
from .llm.modes import Mode, ModeManager
from .llm.ollama import OllamaClient
from .llm.router import Router
from .memory import MemoryIndex, Vault
from .sentinel.service import SentinelService
from .skills.loader import SkillRegistry
from .vision import build_pipeline
from .vision.types import Trigger, TriggerSource

log = logging.getLogger("jarvis.app")


class Jarvis:
    def __init__(self, config: Optional[JarvisConfig] = None) -> None:
        self.cfg = config or load_config(default_config_path())
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.bus = Bus()

        self.ollama = OllamaClient(
            url=self.cfg.llm.ollama_url,
            keep_alive=self.cfg.llm.keep_alive,
            num_ctx=self.cfg.llm.num_ctx,
        )
        self.scheduler = Scheduler(self.bus, self.cfg.scheduler.max_workers)
        self.cache = DiskCache(self.cfg.paths.cache)
        self.router = Router(
            self.ollama,
            l1_fast=self.cfg.llm.l1_fast,
            l1_main=self.cfg.llm.l1_main,
            cache=self.cache,
            max_sentences=self.cfg.persona.max_sentences,
        )
        self.modes = ModeManager(
            self.bus, self.ollama, self.scheduler,
            sleep_after_s=self.cfg.modes.sleep_after_s,
            gaming_detector=make_gaming_detector(self.cfg.modes.gaming.min_gpu_util_pct),
        )
        self.watchdog = GpuWatchdog(
            self.bus, self.modes.force_sleep,
            vram_limit_mb=self.cfg.modes.watchdog.vram_limit_mb,
            temp_limit_c=self.cfg.modes.watchdog.gpu_temp_limit_c,
            poll_interval_s=self.cfg.modes.watchdog.poll_interval_s,
        )
        self.vault = Vault(self.cfg.paths.vault)
        self.memory = MemoryIndex(
            db_path=f"{self.cfg.paths.expanded('cache')}/memory.db",
            vault_root=self.cfg.paths.vault,
        )
        self.skills = SkillRegistry()
        self.actions = ActionGate(
            handlers=build_handlers(self.vault),
            whitelist=self.cfg.actions.whitelist,
            destructive=self.cfg.actions.destructive,
            speak=self.speak,
            log_action=self._log_action,
        )
        self.vision = build_pipeline(
            self.cfg,
            llm_answer=lambda system, user: self.ollama.generate(
                self.cfg.llm.l1_main, user, system=system
            ),
            speak=self.speak,
            vault_store=lambda text: self.vault.daily_append(f"- {text}"),
        )
        self.sentinel = SentinelService(
            self.bus,
            sources=self.cfg.sentinel.sources,
            vault_log=lambda line: self.vault.daily_append(f"- {line}"),
        )
        self.hud = HudState(self.bus, self.scheduler)
        self.bus.subscribe("notify.speak", self._on_notify)

    # --- TTS / bus pomostki ---------------------------------------------------

    def speak(self, text: str) -> None:
        """Wołane też z wątków (akcje, wzrok) — publikuje na bus bezpiecznie."""
        if not text:
            return
        if self.loop is not None:
            self.bus.publish_threadsafe(self.loop, "notify.speak", text)

    async def _on_notify(self, topic, text) -> None:
        # Proaktywne komunikaty (watchdog, sentinel, koniec zadania) → transkrypt HUD-u.
        await self.bus.publish("transcript", {"role": "jarvis", "text": text})

    def _log_action(self, action: str, args: dict, status: str) -> None:
        self.vault.log_action(action, args, status)
        if self.loop is not None:
            self.bus.publish_threadsafe(
                self.loop, "action.logged", {"action": action, "status": status}
            )

    # --- obsługa jednej wypowiedzi -------------------------------------------

    async def handle_utterance(self, text: str) -> list[str]:
        """Zwraca listę zdań odpowiedzi (do TTS). Serce routera L0→L1."""
        self.modes.note_activity()
        await self.bus.publish("transcript", {"role": "ja", "text": text})

        # L0 — regex, 0 tokenów.
        l0 = Router.match_l0(text)
        if l0 is not None:
            answer = await self._run_l0(l0, text)
            if answer is not None:
                await self._remember(text, answer, "l0")
                return _sentences(answer)

        # potrzebny LLM → tryb active (w gaming zostajemy przy L0)
        if self.modes.mode is Mode.GAMING:
            return ["Jestem w trybie gry — tylko podstawowe komendy."]
        await self.modes.ensure_active()

        goal, skill = self.router.classify(text, self.skills.names())
        if goal == "skill":
            answer = await asyncio.to_thread(self._run_skill, skill, text)
            await self._remember(text, answer, "skill")
            return _sentences(answer)
        if goal == "krotka":
            result = self.router.answer_fast(text)
        else:
            recall = self.memory.recall(text, k=4)
            result = self.router.answer_main(text, recall)
        await self._remember(text, result.answer, result.level)
        return _sentences(result.answer)

    async def _run_l0(self, l0, text: str) -> Optional[str]:
        intent = l0.intent
        if intent == "stop_speaking":
            return ""
        if intent == "sleep":
            await self.modes.set_mode(Mode.SLEEP, "polecenie głosowe")
            return "Dobranoc."
        if intent in ("vision_look", "vision_full_screen", "vision_monitor"):
            return await asyncio.to_thread(self._run_vision, intent, text)
        # komendy sterujące i skille deterministyczne
        mapping = {
            "time": ("time", {}),
            "date": ("time", {}),
            "volume_up": ("volume_up", {}),
            "volume_down": ("volume_down", {}),
            "mute": ("mute", {}),
            "media_play_pause": ("media_play_pause", {}),
            "note_add": ("note_add", {"text": l0.args.get("text", "")}),
        }
        if intent in ("time", "date"):
            return await asyncio.to_thread(self._run_skill, "time", text)
        if intent in mapping:
            action, kwargs = mapping[intent]
            trigger = Trigger(TriggerSource.VOICE, text)
            try:
                result = await asyncio.to_thread(
                    self.actions.dispatch, action, trigger, **kwargs
                )
            except PermissionError:
                return ""      # brama już powiedziała odmowę głosem
            return result if isinstance(result, str) else ""
        return None

    def _run_skill(self, skill: str, text: str) -> str:
        try:
            return self.skills.run(skill, {"text": text, "query": text}, ctx=self)
        except Exception as exc:  # noqa: BLE001
            log.exception("skill %s", skill)
            return "Coś poszło nie tak przy realizacji tego zadania."

    def _run_vision(self, intent: str, text: str) -> str:
        from .vision.types import CaptureScope

        scope = CaptureScope.ACTIVE_WINDOW
        monitor_index = 2
        if intent == "vision_full_screen":
            scope = CaptureScope.FULL_SCREEN
        elif intent == "vision_monitor":
            scope = CaptureScope.MONITOR
        result = self.vision.handle(
            text, Trigger(TriggerSource.VOICE, text),
            scope=scope, monitor_index=monitor_index,
            save_requested="zapisz to" in text.lower(),
        )
        return result.answer or result.refusal_reason

    async def _remember(self, text: str, answer: str, level: str) -> None:
        if not answer:
            return
        path = await asyncio.to_thread(
            self.vault.note_interaction, text, answer, level
        )
        await asyncio.to_thread(self.memory.index_file, path)

    # --- cykl życia -----------------------------------------------------------

    async def run(self, with_hud: bool = True) -> None:
        self.loop = asyncio.get_running_loop()
        await self.scheduler.start()
        tasks = [
            asyncio.create_task(self.modes.run()),
            asyncio.create_task(self.watchdog.run()),
            asyncio.create_task(self.sentinel.run()),
        ]
        if with_hud:
            from .hud.server import serve

            tasks.append(asyncio.create_task(serve(self.hud)))
        self._start_voice_thread()
        await asyncio.gather(*tasks)

    def _start_voice_thread(self) -> None:
        from .audio.mic import Microphone
        from .audio.priority import set_low_priority
        from .audio.stt import SpeechToText
        from .audio.tts import make_tts
        from .audio.vad import SileroVad
        from .audio.wake import WakeWord

        set_low_priority()
        mic = Microphone(self.cfg.audio.input_device)
        tts = make_tts(
            self.cfg.audio.tts.engine, self.cfg.audio.tts.voice,
            self.cfg.audio.stt.language, self.cfg.audio.output_device,
        )

        def respond(text: str):
            fut = asyncio.run_coroutine_threadsafe(
                self.handle_utterance(text), self.loop
            )
            for sentence in fut.result():
                yield sentence

        voice = VoiceLoop(
            frames=mic.frames(),
            wake=WakeWord(self.cfg.audio.wake_word.model, self.cfg.audio.wake_word.threshold),
            vad=SileroVad(),
            stt=SpeechToText(
                self.cfg.audio.stt.model, self.cfg.audio.stt.compute_type,
                self.cfg.audio.stt.language,
            ),
            tts=tts,
            respond=respond,
            on_wake=lambda: asyncio.run_coroutine_threadsafe(
                self.modes.on_wake_word(), self.loop
            ),
            on_transcript=lambda role, text: self.bus.publish_threadsafe(
                self.loop, "transcript", {"role": role, "text": text}
            ),
            on_latency=lambda s: self.bus.publish_threadsafe(self.loop, "latency", s),
        )
        self._voice_stop = threading.Event()
        threading.Thread(
            target=voice.run, args=(self._voice_stop,), daemon=True
        ).start()


def _sentences(text: str) -> list[str]:
    from .llm import persona

    return persona.split_sentences(text) or ([text] if text else [])
