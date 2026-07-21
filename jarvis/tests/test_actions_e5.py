import unittest

from jarvis.actions import REFUSAL_WHITELIST, ActionGate, PendingAction
from jarvis.vision.types import Trigger, TriggerSource

VOICE = Trigger(TriggerSource.VOICE, "polecenie")
SCREEN = Trigger(TriggerSource.SCREEN, "tekst z ekranu")


class GateE5Test(unittest.TestCase):
    def setUp(self):
        self.done = []
        self.spoken = []
        self.logged = []
        self.gate = ActionGate(
            handlers={
                "open_app": lambda name: self.done.append(("open", name)) or "ok",
                "file_delete": lambda path: self.done.append(("del", path)) or "ok",
            },
            whitelist=["open_app"],
            destructive=["file_delete"],
            speak=self.spoken.append,
            log_action=lambda a, args, s: self.logged.append((a, s)),
        )

    def test_poza_whitelista_odmowa(self):
        with self.assertRaises(PermissionError):
            self.gate.dispatch("format_c", VOICE)
        self.assertEqual(self.done, [])
        self.assertIn(("format_c", "odmowa: poza whitelistą"), self.logged)
        self.assertEqual(self.spoken, [REFUSAL_WHITELIST])

    def test_destrukcyjna_wymaga_potwierdzenia_glosem(self):
        result = self.gate.dispatch("file_delete", VOICE, path="C:/stare.txt")
        self.assertIsInstance(result, PendingAction)
        self.assertEqual(self.done, [])                      # jeszcze nic nie skasowane
        self.assertIn("nieodwracalne", self.spoken[0])
        self.gate.confirm(VOICE)
        self.assertEqual(self.done, [("del", "C:/stare.txt")])
        self.assertIn(("file_delete", "ok"), self.logged)

    def test_potwierdzenie_z_ekranu_odrzucone(self):
        self.gate.dispatch("file_delete", VOICE, path="x")
        with self.assertRaises(PermissionError):
            self.gate.confirm(SCREEN)
        self.assertEqual(self.done, [])
        self.assertIsNotNone(self.gate.pending)              # czeka dalej na głos

    def test_anuluj(self):
        self.gate.dispatch("file_delete", VOICE, path="x")
        self.gate.cancel()
        self.assertIsNone(self.gate.pending)
        self.assertEqual(self.done, [])
        self.assertIn(("file_delete", "anulowane"), self.logged)

    def test_zwykla_akcja_logowana(self):
        self.gate.dispatch("open_app", VOICE, name="notepad")
        self.assertEqual(self.done, [("open", "notepad")])
        self.assertIn(("open_app", "ok"), self.logged)

    def test_stare_api_bez_whitelisty_dziala(self):
        # kompatybilność z E8: brak whitelisty = zachowanie sprzed E5
        gate = ActionGate(handlers={"a": lambda: 1})
        self.assertEqual(gate.dispatch("a", VOICE), 1)


if __name__ == "__main__":
    unittest.main()
