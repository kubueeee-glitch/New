import os
import tempfile
import unittest

from jarvis.tests.helpers import FakeCapture, FakeOcr, FakeVlm
from jarvis.vision.pipeline import ACK_S2, VisionPipeline
from jarvis.vision.types import CaptureScope, Trigger, TriggerSource, VisionLevel

VOICE = Trigger(TriggerSource.VOICE, "zobacz to")


class PipelineTest(unittest.TestCase):
    def test_s0_pierwszy_dla_aktywnego_okna(self):
        ocr = FakeOcr("tekst z OCR, długi wystarczająco")
        pipeline = VisionPipeline(
            capture=FakeCapture(),
            ocr=ocr,
            vlm=FakeVlm(),
            llm_answer=lambda system, user: "OK",
            s0_reader=lambda: "[Window] Notatnik\n[Edit] Treść dokumentu w polu",
        )
        result = pipeline.handle("co jest napisane", VOICE)
        self.assertIs(result.level, VisionLevel.S0)
        self.assertEqual(ocr.calls, 0)  # S0 wystarczył, OCR nietknięty

    def test_eskalacja_s0_do_s1_gdy_drzewo_puste(self):
        ocr = FakeOcr("tekst z OCR, długi wystarczająco")
        pipeline = VisionPipeline(
            capture=FakeCapture(),
            ocr=ocr,
            vlm=FakeVlm(),
            llm_answer=lambda system, user: "OK",
            s0_reader=lambda: None,
        )
        result = pipeline.handle("co jest napisane", VOICE)
        self.assertIs(result.level, VisionLevel.S1)
        self.assertEqual(ocr.calls, 1)

    def test_eskalacja_do_s2_gdy_brak_tekstu(self):
        spoken = []
        vlm = FakeVlm("Na ekranie jest zdjęcie kota.")
        pipeline = VisionPipeline(
            capture=FakeCapture(),
            ocr=FakeOcr(""),
            vlm=vlm,
            llm_answer=lambda system, user: "OK",
            s0_reader=lambda: None,
            speak=spoken.append,
        )
        result = pipeline.handle("zobacz to", VOICE)
        self.assertIs(result.level, VisionLevel.S2)
        self.assertEqual(spoken, [ACK_S2])  # „Patrzę." zanim VLM zacznie mielić
        self.assertEqual(result.answer, "Na ekranie jest zdjęcie kota.")

    def test_s2_mowi_patrze_przed_vlm(self):
        events = []
        vlm = FakeVlm(events=events)
        pipeline = VisionPipeline(
            capture=FakeCapture(),
            ocr=FakeOcr(""),
            vlm=vlm,
            llm_answer=lambda system, user: "OK",
            s0_reader=lambda: None,
            speak=lambda text: events.append(("tts", text)),
        )
        pipeline.handle("co to za ikona", VOICE)
        self.assertEqual(events[0], ("tts", ACK_S2))
        # potem sekwencja VRAM: zwolnij tekstowy → VLM → wyładuj → przywróć
        payloads = [e[1] for e in events if e[0] == "http"]
        self.assertEqual(payloads[0]["model"], "tekstowy")
        self.assertEqual(payloads[0]["keep_alive"], 0)
        self.assertEqual(payloads[-1]["model"], "tekstowy")
        self.assertEqual(payloads[-1]["keep_alive"], "30m")

    def test_s0_pomijany_poza_aktywnym_oknem(self):
        ocr = FakeOcr("tekst z OCR, długi wystarczająco")
        pipeline = VisionPipeline(
            capture=FakeCapture(),
            ocr=ocr,
            vlm=FakeVlm(),
            llm_answer=lambda system, user: "OK",
            s0_reader=lambda: self.fail("S0 czyta tylko aktywne okno"),
        )
        result = pipeline.handle(
            "co jest napisane", VOICE, scope=CaptureScope.FULL_SCREEN
        )
        self.assertIs(result.level, VisionLevel.S1)

    def test_zapis_tylko_na_jawne_zyczenie(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = VisionPipeline(
                capture=FakeCapture(),
                ocr=FakeOcr("tekst z OCR, długi wystarczająco"),
                vlm=FakeVlm(),
                llm_answer=lambda system, user: "OK",
                s0_reader=lambda: None,
                save_dir=tmp,
            )
            result = pipeline.handle("zobacz to", VOICE)
            self.assertEqual(result.saved_to, "")
            self.assertEqual(os.listdir(tmp), [])  # nic nie dotknęło dysku


if __name__ == "__main__":
    unittest.main()
