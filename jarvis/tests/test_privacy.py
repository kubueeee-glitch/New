import unittest

from jarvis.tests.helpers import FakeCapture, FakeOcr, FakeVlm
from jarvis.vision.pipeline import REFUSAL_NOT_VOICE, VisionPipeline
from jarvis.vision.privacy import PrivacyGuard
from jarvis.vision.types import Trigger, TriggerSource


def make_pipeline(**kw):
    defaults = dict(
        capture=FakeCapture(),
        ocr=FakeOcr("Jakiś tekst z ekranu, wystarczająco długi."),
        vlm=FakeVlm(),
        llm_answer=lambda system, user: "Odpowiedź.",
        s0_reader=lambda: None,
    )
    defaults.update(kw)
    return VisionPipeline(**defaults)


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.guard = PrivacyGuard(["KeePass", "1Password", "*bank*", "PKO"])

    def test_wykluczenia(self):
        self.assertTrue(self.guard.is_excluded("KeePassXC — baza haseł"))
        self.assertTrue(self.guard.is_excluded("mBank — logowanie"))
        self.assertTrue(self.guard.is_excluded("iPKO — moje konto"))
        self.assertFalse(self.guard.is_excluded("Notatnik — plik.txt"))
        self.assertFalse(self.guard.is_excluded(""))


class PipelinePrivacyTest(unittest.TestCase):
    def test_wykluczenie_okna_odmowa_bez_zrzutu(self):
        capture = FakeCapture(title="KeePassXC — baza haseł")
        spoken = []
        pipeline = make_pipeline(
            capture=capture,
            guard=PrivacyGuard(["KeePass"]),
            speak=spoken.append,
        )
        result = pipeline.handle("zobacz to", Trigger(TriggerSource.VOICE, "zobacz to"))
        self.assertTrue(result.refused)
        self.assertEqual(capture.grabs, [])  # piksele nigdy nie zostały pobrane
        self.assertEqual(spoken, [PrivacyGuard.SPOKEN_REFUSAL])

    def test_zrzut_tylko_na_komende_glosowa(self):
        capture = FakeCapture()
        pipeline = make_pipeline(capture=capture)
        for source in (TriggerSource.SCREEN, TriggerSource.SYSTEM):
            result = pipeline.handle("zobacz to", Trigger(source, "zobacz to"))
            self.assertTrue(result.refused)
            self.assertEqual(result.refusal_reason, REFUSAL_NOT_VOICE)
        self.assertEqual(capture.grabs, [])

    def test_zrzut_zerowany_po_odpowiedzi(self):
        capture = FakeCapture()
        pipeline = make_pipeline(capture=capture)
        result = pipeline.handle("zobacz to", Trigger(TriggerSource.VOICE, "zobacz to"))
        self.assertFalse(result.refused)
        self.assertEqual(len(capture.last_shot.data), 0)  # wipe() zadziałał

    def test_do_vaulta_trafia_tylko_tekst(self):
        vault = []
        pipeline = make_pipeline(vault_store=vault.append)
        pipeline.handle("zobacz to", Trigger(TriggerSource.VOICE, "zobacz to"))
        self.assertEqual(len(vault), 1)
        self.assertIsInstance(vault[0], str)
        self.assertIn("Odpowiedź.", vault[0])


if __name__ == "__main__":
    unittest.main()
