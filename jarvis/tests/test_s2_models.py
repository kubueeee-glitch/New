import unittest

from jarvis.vision.s2_vlm import VlmClient
from jarvis.vision.vram import VramManager


def make_client(**kw):
    vram = VramManager(text_model="tekstowy", http=lambda url, payload: {})
    defaults = dict(
        default_model="qwen2.5vl:7b",
        fast_model="moondream2",
        code_ui_model="internvl2.5:8b",
    )
    defaults.update(kw)
    return VlmClient(vram, **defaults)


class PickModelTest(unittest.TestCase):
    def test_proste_pytanie_moondream(self):
        client = make_client(code_ui_model="")
        self.assertEqual(client.pick_model("co to za ikona"), "moondream2")

    def test_dluzsze_pytanie_domyslny(self):
        client = make_client(code_ui_model="")
        self.assertEqual(
            client.pick_model(
                "porównaj oba wykresy i powiedz który pokazuje większy wzrost w tym roku"
            ),
            "qwen2.5vl:7b",
        )

    def test_kod_i_interfejs_internvl(self):
        client = make_client()
        self.assertEqual(client.pick_model("co robi ten kod"), "internvl2.5:8b")
        self.assertEqual(
            client.pick_model("oceń układ tego interfejsu"), "internvl2.5:8b"
        )

    def test_ui_nie_lapie_sie_w_srodku_slowa(self):
        client = make_client(fast_model="")
        self.assertEqual(
            client.pick_model("czy ten ekran wydaje się intuicyjny w obsłudze dla nowych osób"),
            "qwen2.5vl:7b",
        )


if __name__ == "__main__":
    unittest.main()
