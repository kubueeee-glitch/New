import unittest

from jarvis.vision.router import VisionRouter
from jarvis.vision.types import VisionLevel


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.router = VisionRouter()

    def test_pytania_o_tekst_ida_tania_sciezka(self):
        for q in (
            "przeczytaj ten błąd",
            "co jest napisane w tym oknie",
            "streść ten artykuł",
            "co mówi ten komunikat",
            "pomóż mi z tym formularzem",
            "zobacz ten kod",
        ):
            self.assertIs(self.router.choose_level(q), VisionLevel.S0, q)

    def test_pytania_wizualne_ida_do_s2(self):
        for q in (
            "co to za ikona przy zegarze",
            "opisz ten wykres",
            "co jest na tym zdjęciu",
            "jak wygląda ten układ",
        ):
            self.assertIs(self.router.choose_level(q), VisionLevel.S2, q)

    def test_gesty_tekst_wygrywa_z_wizualnym(self):
        # „Przy gęstym tekście preferuj S1" — wskazówka tekstowa bije wykres.
        self.assertIs(
            self.router.choose_level("przeczytaj tekst z tego wykresu"),
            VisionLevel.S0,
        )

    def test_brak_wskazowek_startuje_tanio(self):
        self.assertIs(self.router.choose_level("zobacz to"), VisionLevel.S0)


if __name__ == "__main__":
    unittest.main()
