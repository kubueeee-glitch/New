import os
import tempfile
import unittest
from datetime import datetime

from jarvis.memory import MemoryIndex, Vault

WHEN = datetime(2026, 7, 21, 14, 30, 15)


class VaultTest(unittest.TestCase):
    def test_interakcja_frontmatter_i_wikilinki(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(tmp)
            path = vault.note_interaction(
                "zapamiętaj że lubię kawę", "Zapamiętane.", level="l1_main", when=WHEN
            )
            content = open(path, encoding="utf-8").read()
            self.assertTrue(content.startswith("---\n"))
            self.assertIn("type: interakcja", content)
            self.assertIn("[[2026-07-21]]", content)       # wikilink do daily
            self.assertIn("lubię kawę", content)
            daily = open(os.path.join(tmp, "daily", "2026-07-21.md"), encoding="utf-8").read()
            self.assertIn("14:30", daily)

    def test_daily_naglowek_raz(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(tmp)
            vault.daily_append("- raz", WHEN)
            vault.daily_append("- dwa", WHEN)
            daily = open(os.path.join(tmp, "daily", "2026-07-21.md"), encoding="utf-8").read()
            self.assertEqual(daily.count("# 2026-07-21"), 1)
            self.assertIn("- raz\n- dwa\n", daily)

    def test_log_akcji(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(tmp)
            vault.log_action("open_app", {"name": "notepad"}, "ok", WHEN)
            daily = open(os.path.join(tmp, "daily", "2026-07-21.md"), encoding="utf-8").read()
            self.assertIn("AKCJA `open_app` name=notepad [ok]", daily)


class IndexTest(unittest.TestCase):
    def test_recall_fragmenty_nie_cale_pliki(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(tmp)
            long_note = "O kawie.\n\n" + "\n\n".join(
                f"Akapit {i} o niczym szczególnym." for i in range(30)
            ) + "\n\nUżytkownik pija kawę przelewową, bez cukru."
            path = vault._write("notatki/kawa.md", long_note)
            index = MemoryIndex(os.path.join(tmp, "index.db"), tmp)
            index.index_file(path)
            hits = index.recall("kawa przelewowa", k=5)
            self.assertTrue(hits)
            self.assertTrue(any("przelewow" in h for h in hits))
            for h in hits:
                self.assertLess(len(h), len(long_note))    # fragment, nie plik
                self.assertIn("(notatki/kawa.md)", h)

    def test_recall_max_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = MemoryIndex(os.path.join(tmp, "index.db"), tmp)
            for i in range(10):
                index.index_text(f"n{i}.md", f"wpis numer {i} o herbacie zielonej")
            self.assertLessEqual(len(index.recall("herbata zielona", k=50)), 5)

    def test_rebuild_indeksuje_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(tmp)
            vault.note_interaction("kod PIN do sejfu to żart", "Rozumiem.", when=WHEN)
            index = MemoryIndex(os.path.join(tmp, ".jarvis-index.db"), tmp)
            count = index.rebuild()
            self.assertGreaterEqual(count, 2)              # interakcja + daily
            self.assertTrue(index.recall("sejf"))

    def test_puste_zapytanie(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = MemoryIndex(os.path.join(tmp, "i.db"), tmp)
            self.assertEqual(index.recall("  !?  "), [])


if __name__ == "__main__":
    unittest.main()
