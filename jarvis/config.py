"""Konfiguracja Jarvisa — jedno źródło prawdy: jarvis/config.yaml."""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from typing import Any, Optional


def _d(raw: Any, key: str) -> dict:
    value = (raw or {}).get(key)
    return value if isinstance(value, dict) else {}


def _fill(cls, raw: dict, **overrides):
    names = {f.name for f in dataclasses.fields(cls)}
    kwargs = {k: raw[k] for k in raw if k in names}
    kwargs.update(overrides)
    return cls(**kwargs)


@dataclass
class PathsSettings:
    vault: str = "~/JarvisVault"
    cache: str = "~/.jarvis/cache"
    logs: str = "~/.jarvis/logs"

    def expanded(self, name: str) -> str:
        return os.path.expanduser(getattr(self, name))


@dataclass
class WakeWordSettings:
    engine: str = "openwakeword"
    model: str = "hey_jarvis"
    threshold: float = 0.5


@dataclass
class SttSettings:
    engine: str = "faster-whisper"
    model: str = "small"
    compute_type: str = "int8"
    language: str = "pl"


@dataclass
class TtsSettings:
    engine: str = "kokoro"
    model: str = "Kokoro-82M"
    voice: str = ""


@dataclass
class AudioSettings:
    input_device: Optional[int] = None
    output_device: Optional[int] = None
    torch_num_threads: int = 4
    process_priority: str = "BELOW_NORMAL_PRIORITY_CLASS"
    vad_engine: str = "silero"
    wake_word: WakeWordSettings = field(default_factory=WakeWordSettings)
    stt: SttSettings = field(default_factory=SttSettings)
    tts: TtsSettings = field(default_factory=TtsSettings)


@dataclass
class L2Settings:
    enabled: bool = False
    provider: str = ""
    api_key_env: str = ""


@dataclass
class LlmSettings:
    ollama_url: str = "http://127.0.0.1:11434"
    keep_alive: int = 300
    num_ctx: int = 8192
    kv_cache_type: str = "q8_0"
    flash_attention: bool = True
    l1_fast: str = "qwen3:4b"
    l1_main: str = "qwen3.5:9b"
    l2: L2Settings = field(default_factory=L2Settings)


@dataclass
class GamingSettings:
    fullscreen_process: bool = True
    min_gpu_util_pct: int = 10


@dataclass
class WatchdogSettings:
    vram_limit_mb: int = 6800
    gpu_temp_limit_c: int = 80
    poll_interval_s: int = 5


@dataclass
class ModesSettings:
    sleep_after_s: int = 300
    gaming: GamingSettings = field(default_factory=GamingSettings)
    watchdog: WatchdogSettings = field(default_factory=WatchdogSettings)


@dataclass
class SchedulerSettings:
    max_workers: int = 3


@dataclass
class PersonaSettings:
    max_sentences: int = 2
    first_sound_target_ms: int = 800


@dataclass
class ActionsSettings:
    whitelist: list[str] = field(default_factory=list)
    destructive: list[str] = field(default_factory=list)


@dataclass
class SentinelSettings:
    read_only: bool = True
    sources: dict = field(default_factory=dict)
    virustotal_api_key_env: str = "JARVIS_VT_API_KEY"


@dataclass
class S2Settings:
    default_model: str = "qwen2.5vl:7b"      # dobry OCR i rozumienie zrzutów
    fast_model: str = "moondream"            # moondream2; tag w Ollamie: moondream
    code_ui_model: str = ""                  # np. InternVL 2.5 8B do kodu/UI


@dataclass
class VisionSettings:
    max_long_side: int = 1024
    ollama_url: str = "http://127.0.0.1:11434"
    text_model: str = ""                     # model tekstowy przywracany po S2
    save_dir: str = "."
    s2: S2Settings = field(default_factory=S2Settings)


@dataclass
class PrivacySettings:
    excluded_windows: list[str] = field(default_factory=list)


@dataclass
class JarvisConfig:
    paths: PathsSettings = field(default_factory=PathsSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    llm: LlmSettings = field(default_factory=LlmSettings)
    modes: ModesSettings = field(default_factory=ModesSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    persona: PersonaSettings = field(default_factory=PersonaSettings)
    actions: ActionsSettings = field(default_factory=ActionsSettings)
    sentinel: SentinelSettings = field(default_factory=SentinelSettings)
    vision: VisionSettings = field(default_factory=VisionSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)


def default_config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config(path: str = "config.yaml") -> JarvisConfig:
    cfg = JarvisConfig()
    if not os.path.exists(path):
        return cfg
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg.paths = _fill(PathsSettings, _d(raw, "paths"))

    a = _d(raw, "audio")
    cfg.audio = _fill(
        AudioSettings,
        a,
        vad_engine=str(_d(a, "vad").get("engine", "silero")),
        wake_word=_fill(WakeWordSettings, _d(a, "wake_word")),
        stt=_fill(SttSettings, _d(a, "stt")),
        tts=_fill(TtsSettings, _d(a, "tts")),
    )

    l = _d(raw, "llm")
    lv = _d(l, "levels")
    cfg.llm = _fill(
        LlmSettings,
        l,
        l1_fast=str(lv.get("l1_fast", cfg.llm.l1_fast)),
        l1_main=str(lv.get("l1_main", cfg.llm.l1_main)),
        l2=_fill(L2Settings, _d(lv, "l2")),
    )

    m = _d(raw, "modes")
    cfg.modes = _fill(
        ModesSettings,
        m,
        gaming=_fill(GamingSettings, _d(m, "gaming")),
        watchdog=_fill(WatchdogSettings, _d(m, "watchdog")),
    )

    cfg.scheduler = _fill(SchedulerSettings, _d(raw, "scheduler"))
    cfg.persona = _fill(PersonaSettings, _d(raw, "persona"))
    cfg.actions = _fill(ActionsSettings, _d(raw, "actions"))
    cfg.sentinel = _fill(SentinelSettings, _d(raw, "sentinel"))

    v = _d(raw, "vision")
    cfg.vision = _fill(VisionSettings, v, s2=_fill(S2Settings, _d(v, "s2")))
    cfg.privacy = _fill(PrivacySettings, _d(raw, "privacy"))
    return cfg
