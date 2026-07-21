import asyncio
import tempfile
import unittest

from jarvis.core.bus import Bus
from jarvis.core.scheduler import Scheduler
from jarvis.llm import persona
from jarvis.llm.cache import DiskCache
from jarvis.llm.gpu import GpuWatchdog, make_gaming_detector
from jarvis.llm.modes import Mode, ModeManager
from jarvis.llm.ollama import OllamaClient
from jarvis.llm.router import Router


def make_ollama(responses=None, calls=None):
    calls = calls if calls is not None else []

    def http(path, payload):
        calls.append(payload)
        return {"response": (responses or {}).get(payload.get("model"), "Odpowiedź.")}

    client = OllamaClient(http=http)
    client._calls = calls
    return client


class L0Test(unittest.TestCase):
    def test_komendy_deterministyczne(self):
        cases = {
            "która godzina": "time",
            "która jest godzina?": "time",
            "zrób głośniej": "volume_up",
            "wycisz": "mute",
            "pauza": "media_play_pause",
            "zobacz to": "vision_look",
            "zobacz cały ekran": "vision_full_screen",
            "idź spać": "sleep",
            "stop": "stop_speaking",
        }
        for text, intent in cases.items():
            result = Router.match_l0(text)
            self.assertIsNotNone(result, text)
            self.assertEqual(result.intent, intent, text)

    def test_notatka_z_trescia(self):
        result = Router.match_l0("zapisz notatkę kupić mleko i chleb")
        self.assertEqual(result.intent, "note_add")
        self.assertEqual(result.args["text"], "kupić mleko i chleb")

    def test_zwykle_pytanie_nie_jest_l0(self):
        self.assertIsNone(Router.match_l0("co sądzisz o tej książce"))


class PersonaTest(unittest.TestCase):
    def test_maksymalnie_dwa_zdania(self):
        text = "Pierwsze zdanie. Drugie zdanie. Trzecie zdanie. Czwarte."
        self.assertEqual(persona.enforce(text), "Pierwsze zdanie. Drugie zdanie.")

    def test_preambula_zdjeta(self):
        self.assertEqual(persona.enforce("Jasne! Jest 14:30."), "Jest 14:30.")
        self.assertEqual(persona.enforce("Oczywiście, już mówię. Jest wtorek."),
                         "już mówię. Jest wtorek.")

    def test_jedno_zdanie_gdy_limit_1(self):
        self.assertEqual(persona.enforce("Raz. Dwa.", max_sentences=1), "Raz.")


class OllamaSingleModelTest(unittest.TestCase):
    def test_zwalnia_poprzedni_przed_nastepnym(self):
        client = make_ollama()
        client.generate("qwen3:4b", "a")
        client.generate("qwen3.5:9b", "b")
        payloads = client._calls
        # 4b załadowany → przed 9b musi pójść unload 4b (keep_alive 0)
        self.assertEqual(payloads[1], {"model": "qwen3:4b", "prompt": "", "keep_alive": 0})
        self.assertEqual(payloads[2]["model"], "qwen3.5:9b")
        self.assertEqual(client.loaded, "qwen3.5:9b")

    def test_unload_all_zeruje_vram(self):
        client = make_ollama()
        client.generate("qwen3:4b", "a")
        client.unload_all()
        self.assertIsNone(client.loaded)
        self.assertEqual(client._calls[-1]["keep_alive"], 0)


class RouterTest(unittest.TestCase):
    def test_classify_json(self):
        client = make_ollama(responses={"qwen3:4b": '{"cel": "skill", "skill": "time"}'})
        router = Router(client, "qwen3:4b", "qwen3.5:9b")
        self.assertEqual(router.classify("która godzina", ["time"]), ("skill", "time"))

    def test_classify_smieci_to_rozmowa(self):
        client = make_ollama(responses={"qwen3:4b": "nie wiem"})
        router = Router(client, "qwen3:4b", "qwen3.5:9b")
        self.assertEqual(router.classify("hmm", []), ("rozmowa", ""))

    def test_cache_dziala(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            client = make_ollama(responses={"qwen3:4b": '{"cel":"krotka"}'}, calls=calls)
            router = Router(client, "qwen3:4b", "qwen3.5:9b", cache=DiskCache(tmp))
            router.classify("która godzina", [])
            n = len(calls)
            router.classify("która godzina", [])
            self.assertEqual(len(calls), n)  # drugi raz z cache, zero wywołań

    def test_historia_w_promptcie_main(self):
        prompts = []

        def http(path, payload):
            prompts.append(payload.get("prompt", ""))
            return {"response": "Dobrze."}

        client = OllamaClient(http=http)
        router = Router(client, "qwen3:4b", "qwen3.5:9b")
        router.answer_main("zapamiętaj że lubię kawę")
        router.answer_main("co lubię pić?")
        self.assertIn("zapamiętaj że lubię kawę", prompts[-1])  # ciągłość


class ModesTest(unittest.TestCase):
    def _make(self, detector=None):
        self.now = 0.0
        bus = Bus()
        self.events = []
        bus.subscribe("mode.changed", lambda t, p: self.events.append(p["new"]))
        bus.subscribe("notify.speak", lambda t, p: self.events.append(("speak", p)))
        client = make_ollama()
        sched = Scheduler(bus)
        mm = ModeManager(
            bus, client, sched, sleep_after_s=300,
            gaming_detector=detector, clock=lambda: self.now,
        )
        return mm, client, sched

    def test_sleep_po_5_minutach(self):
        mm, client, _ = self._make()
        asyncio.run(self._idle_flow(mm))
        self.assertIs(mm.mode, Mode.SLEEP)
        self.assertIsNone(client.loaded)

    async def _idle_flow(self, mm):
        await mm.on_wake_word()
        self.assertIs(mm.mode, Mode.LISTEN)
        await mm.ensure_active()
        self.assertIs(mm.mode, Mode.ACTIVE)
        self.now = 301.0
        await mm.tick()

    def test_gaming_pauzuje_kolejke_i_zwalnia_vram(self):
        gaming = {"on": False}
        mm, client, sched = self._make(detector=lambda: gaming["on"])

        async def flow():
            await mm.ensure_active()
            client.generate("qwen3.5:9b", "x")
            gaming["on"] = True
            await mm.tick()
            self.assertIs(mm.mode, Mode.GAMING)
            self.assertIsNone(client.loaded)
            self.assertTrue(sched.paused)
            gaming["on"] = False
            await mm.tick()
            self.assertIs(mm.mode, Mode.LISTEN)
            self.assertFalse(sched.paused)

        asyncio.run(flow())

    def test_force_sleep_mowi_glosem(self):
        mm, _, _ = self._make()

        async def flow():
            await mm.ensure_active()
            await mm.force_sleep("temperatura karty 83 stopni")

        asyncio.run(flow())
        self.assertIs(mm.mode, Mode.SLEEP)
        spoken = [p for p in self.events if isinstance(p, tuple) and p[0] == "speak"]
        self.assertIn("temperatura", spoken[0][1])


class WatchdogTest(unittest.TestCase):
    def test_przekroczenie_vram_wymusza_sen(self):
        slept = []

        async def force_sleep(reason):
            slept.append(reason)

        wd = GpuWatchdog(
            Bus(), force_sleep, vram_limit_mb=6800, temp_limit_c=80,
            stats_reader=lambda: {"vram_used_mb": 7000, "vram_total_mb": 8192,
                                  "temp_c": 60, "power_w": 120.0, "util_pct": 50},
        )
        asyncio.run(wd.check_once())
        self.assertEqual(len(slept), 1)
        self.assertIn("VRAM", slept[0])

    def test_temperatura_wymusza_sen(self):
        slept = []

        async def force_sleep(reason):
            slept.append(reason)

        wd = GpuWatchdog(
            Bus(), force_sleep,
            stats_reader=lambda: {"vram_used_mb": 100, "vram_total_mb": 8192,
                                  "temp_c": 85, "power_w": 120.0, "util_pct": 50},
        )
        asyncio.run(wd.check_once())
        self.assertIn("85", slept[0])

    def test_detektor_gamingu(self):
        detect = make_gaming_detector(
            min_gpu_util_pct=10,
            stats_reader=lambda: {"util_pct": 42, "vram_used_mb": 0,
                                  "vram_total_mb": 0, "temp_c": 0, "power_w": 0},
            fullscreen_check=lambda: True,
        )
        self.assertTrue(detect())
        detect2 = make_gaming_detector(
            stats_reader=lambda: {"util_pct": 2, "vram_used_mb": 0,
                                  "vram_total_mb": 0, "temp_c": 0, "power_w": 0},
            fullscreen_check=lambda: True,
        )
        self.assertFalse(detect2())


class StreamTest(unittest.TestCase):
    def test_strumien_zdan_ucina_po_dwoch(self):
        chunks = ["Pierwsze ", "zdanie. Drugie zda", "nie. Trzecie zdanie. Czwarte."]

        def http_stream(path, payload):
            for c in chunks:
                yield {"response": c}
            yield {"done": True}

        client = OllamaClient(http=lambda p, d: {"response": ""}, http_stream=http_stream)
        router = Router(client, "qwen3:4b", "qwen3.5:9b")
        sentences = list(router.answer_main_stream("opowiedz coś"))
        self.assertEqual(sentences, ["Pierwsze zdanie.", "Drugie zdanie."])


if __name__ == "__main__":
    unittest.main()
