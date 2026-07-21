"""Wybór poziomu S0/S1/S2 — robi go L1-fast na podstawie treści pytania.

Trójstopniowa ścieżka, analogiczna do routera LLM:
- pytania o TEKST (błąd, kod, artykuł, formularz) → ścieżka tekstowa
  (S0, z eskalacją do S1) — model wizyjny jest do tego niepotrzebny,
- pytania o wykresy, układ UI, zdjęcia, „co to za ikona" → S2,
- przy gęstym tekście zawsze preferuj S1: wskazówki tekstowe wygrywają
  ze wskazówkami wizualnymi.
"""
from __future__ import annotations

from .types import VisionLevel

TEXT_HINTS = (
    "błąd",
    "błędzie",
    "error",
    "napisane",
    "napisano",
    "pisze",
    "tekst",
    "treść",
    "kod",
    "artykuł",
    "formularz",
    "przeczytaj",
    "odczytaj",
    "komunikat",
    "wiadomoś",
    "mail",
    "log",
)

S2_HINTS = (
    "wykres",
    "diagram",
    "ikona",
    "ikonka",
    "ikonę",
    "zdjęci",
    "obraz",
    "obrazek",
    "grafik",
    "wygląda",
    "układ",
    "layout",
    "kolor",
    "mapa",
    "mapie",
)


class VisionRouter:
    def __init__(self, text_hints=TEXT_HINTS, s2_hints=S2_HINTS) -> None:
        self.text_hints = tuple(text_hints)
        self.s2_hints = tuple(s2_hints)

    def choose_level(self, question: str) -> VisionLevel:
        q = question.lower()
        if any(h in q for h in self.text_hints):
            return VisionLevel.S0
        if any(h in q for h in self.s2_hints):
            return VisionLevel.S2
        # „zobacz to" bez wskazówek: większość pytań o ekran dotyczy tekstu,
        # więc startujemy tanio (S0→S1); pipeline eskaluje do S2, gdy tekstu brak.
        return VisionLevel.S0
