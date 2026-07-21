import unittest

from jarvis.vision.vram import VramManager


class VramTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.vram = VramManager(
            text_model="tekstowy",
            http=lambda url, payload: self.calls.append(payload) or {},
        )

    def test_sekwencja_zwolnij_zaladuj_przywroc(self):
        with self.vram.vlm_session("qwen2.5vl:7b"):
            self.calls.append({"marker": "vlm_odpowiada"})

        # zwolnij model tekstowy → [VLM odpowiada] → wyładuj VLM → przywróć tekstowy
        self.assertEqual(self.calls[0], {"model": "tekstowy", "prompt": "", "keep_alive": 0})
        self.assertEqual(self.calls[1], {"marker": "vlm_odpowiada"})
        self.assertEqual(self.calls[2], {"model": "qwen2.5vl:7b", "prompt": "", "keep_alive": 0})
        self.assertEqual(self.calls[3], {"model": "tekstowy", "prompt": "", "keep_alive": "30m"})
        self.assertEqual(len(self.calls), 4)

    def test_model_tekstowy_wraca_nawet_po_bledzie(self):
        with self.assertRaises(RuntimeError):
            with self.vram.vlm_session("qwen2.5vl:7b"):
                raise RuntimeError("VLM padł")
        self.assertEqual(self.calls[-1], {"model": "tekstowy", "prompt": "", "keep_alive": "30m"})

    def test_nigdy_dwa_modele_naraz(self):
        with self.vram.vlm_session("a"):
            with self.assertRaises(RuntimeError):
                with self.vram.vlm_session("b"):
                    pass


if __name__ == "__main__":
    unittest.main()
