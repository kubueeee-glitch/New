"""Twarde reguły prywatności etapu E8.

- Zrzut wyłącznie na jawną komendę głosową (egzekwuje pipeline).
- Zero przechwytywania w tle — nie istnieje żadna pętla ani timer robiący zrzuty.
- Zrzuty żyją tylko w pamięci; zapis na dysk wyłącznie po jawnym „zapisz to".
- Okna z listy wykluczeń (menedżer haseł, bankowość, wskazane aplikacje)
  → odmowa zrzutu i komunikat głosowy.
- Do vaulta trafia wyłącznie tekstowe streszczenie, nigdy obraz.
"""
from __future__ import annotations

import fnmatch
from typing import Iterable


class PrivacyGuard:
    SPOKEN_REFUSAL = "To okno jest na liście prywatnych — nie robię zrzutu."

    def __init__(self, excluded_patterns: Iterable[str] = ()):
        self._patterns = [p.strip().lower() for p in excluded_patterns if p.strip()]

    def is_excluded(self, window_title: str = "", process_name: str = "") -> bool:
        """Wzorzec z `*`/`?` działa jak fnmatch, zwykły — jak dopasowanie fragmentu."""
        for subject in (window_title, process_name):
            if not subject:
                continue
            s = subject.lower()
            for p in self._patterns:
                if "*" in p or "?" in p:
                    if fnmatch.fnmatch(s, p):
                        return True
                elif p in s:
                    return True
        return False
