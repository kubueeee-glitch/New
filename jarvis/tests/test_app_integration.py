"""Test spięcia całości (E1–E8): orkiestrator routuje i pamięta bez sprzętu."""
import asyncio
import tempfile
import unittest

from jarvis.app import Jarvis
from jarvis.config import (
    ActionsSettings,
    JarvisConfig,
    LlmSettings,
    PathsSettings,
    VisionSettings,
)


def make_jarvis(tmp, ollama_responses=None):
    cfg = JarvisConfig()
    cfg.paths = PathsSettings(vault=f"{tmp}/vault", cache=f"{tmp}/cache", logs=f"{tmp}/logs")
    cfg.llm = LlmSettings(l1_fast="qwen3:4b", l1_main="qwen3.5:9b")
    cfg.actions = ActionsSettings(
        whitelist=["open_app", "volume_up", "volume_down", "mute", "media_play_pause", "note_add"],
        destructive=["file_delete"],
    )
    cfg.vision = VisionSettings(text_model="qwen3.5:9b", save_dir=f"{tmp}/shots")
    jarvis = Jarvis(cfg)

    # fałszywy Ollama — brak sieci, brak VRAM.
    # Klucz "classify" → odpowiedź routera intencji (model l1-fast + system routera);
    # pozostałe klucze dopasowują się do treści promptu.
    responses = ollama_responses or {}

    def fake_generate(model, prompt, system=""):
        if "routerem intencji" in system:
            return responses.get("classify", '{"cel": "rozmowa"}')
        for key, val in responses.items():
            if key in ("classify",):
                continue
            if key in prompt:
                return val
        return responses.get(model, "Odpowiedź testowa.")

    jarvis.ollama.generate = fake_generate
    jarvis.loop = asyncio.get_event_loop()
    return jarvis


class AppIntegrationTest(unittest.TestCase):
    def test_l0_czas_bez_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            async def flow():
                jarvis = make_jarvis(tmp)
                # gdyby dotknął LLM — rzuci; L0 nie może go dotknąć
                jarvis.ollama.generate = lambda *a, **k: (_ for _ in ()).throw(
                    AssertionError("L0 nie powinno wołać LLM")
                )
                return await jarvis.handle_utterance("która godzina")
            sentences = asyncio.run(flow())
            self.assertTrue(any("Jest " in s for s in sentences))

    def test_rozmowa_idzie_do_l1_main_z_pamiecia(self):
        with tempfile.TemporaryDirectory() as tmp:
            async def flow():
                jarvis = make_jarvis(tmp, {
                    "classify": '{"cel": "rozmowa"}',
                    "qwen3.5:9b": "Rozumiem, wolisz kawę przelewową.",
                })
                await jarvis.scheduler.start()
                out = await jarvis.handle_utterance("wolę kawę przelewową bez cukru")
                await jarvis.scheduler.stop()
                return jarvis, out
            jarvis, out = asyncio.run(flow())
            self.assertTrue(out)
            # interakcja trafiła do vaulta i indeksu
            self.assertTrue(jarvis.memory.recall("kawa przelewowa"))

    def test_skill_wybrany_przez_router(self):
        with tempfile.TemporaryDirectory() as tmp:
            async def flow():
                jarvis = make_jarvis(tmp, {"classify": '{"cel":"skill","skill":"time"}'})
                await jarvis.scheduler.start()
                out = await jarvis.handle_utterance("powiedz mi która jest teraz")
                await jarvis.scheduler.stop()
                return out
            # uwaga: "która ... teraz" nie łapie L0 (brak słowa godzina), więc idzie do routera
            out = asyncio.run(flow())
            self.assertTrue(any("Jest " in s for s in out))

    def test_akcja_glosowa_przez_l0(self):
        with tempfile.TemporaryDirectory() as tmp:
            async def flow():
                jarvis = make_jarvis(tmp)
                out = await jarvis.handle_utterance("zrób głośniej")
                return jarvis, out
            jarvis, out = asyncio.run(flow())
            self.assertIn("volume_up", [a for a, _ in jarvis.actions.log])

    def test_wzrok_przez_l0_to_dane_nie_akcje(self):
        with tempfile.TemporaryDirectory() as tmp:
            async def flow():
                jarvis = make_jarvis(tmp, {"screen_content": "Opis ekranu."})
                # podstawiamy fałszywy pipeline wzroku: zwraca opis, nie wykonuje akcji
                from jarvis.vision.types import VisionLevel, VisionResult
                jarvis.vision.handle = lambda *a, **k: VisionResult(
                    answer="Widzę stronę z tekstem.", level=VisionLevel.S1
                )
                return await jarvis.handle_utterance("zobacz to")
            out = asyncio.run(flow())
            self.assertIn("Widzę stronę z tekstem.", " ".join(out))

    def test_gaming_blokuje_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            async def flow():
                jarvis = make_jarvis(tmp)
                from jarvis.llm.modes import Mode
                await jarvis.modes.set_mode(Mode.GAMING, "test")
                return await jarvis.handle_utterance("opowiedz mi o wszechświecie")
            out = asyncio.run(flow())
            self.assertIn("trybie gry", " ".join(out))


if __name__ == "__main__":
    unittest.main()
