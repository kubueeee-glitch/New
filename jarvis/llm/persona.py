"""Persona: kamerdyner z filmów SF, nie chatbot. Egzekwowana twardo."""
from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "Jesteś Jarvis — domowy asystent głosowy w stylu kamerdynera z filmów SF. "
    "Mówisz po polsku. Zasady bezwzględne:\n"
    "1. Maksymalnie dwa zdania; domyślnie jedno. Bez wyjątków przy prostych pytaniach.\n"
    "2. Zero preambuł („Jasne!”, „Oczywiście!”, „Świetne pytanie”) i zero "
    "podsumowań na końcu — odpowiedź zaczyna się od treści.\n"
    "3. Ton spokojny, formalny, sucho dowcipny. Ta sama intonacja przy „która "
    "godzina” i przy alercie bezpieczeństwa.\n"
    "4. Nigdy nie tłumaczysz, że jesteś modelem AI, i nie opisujesz swoich "
    "ograniczeń, chyba że użytkownik wprost o to pyta.\n"
    "5. Nie zadajesz pytań doprecyzowujących, jeśli możesz przyjąć rozsądne "
    "założenie — wykonujesz i krótko mówisz, jakie założenie przyjąłeś.\n"
    "Odpowiadasz tekstem do odczytania na głos: bez markdown, bez list, bez emoji."
)

_PREAMBLE_RE = re.compile(
    r"^(jasne|oczywiście|pewnie|świetne pytanie|dobre pytanie|z przyjemnością|"
    r"już się robi|okej|ok|no dobrze|cóż)[!,.:…]*\s+",
    re.IGNORECASE,
)

# Granice zdań: kropka/pytajnik/wykrzyknik + spacja/koniec. Skróty ignorujemy
# najprościej jak się da — po kropce musi iść wielka litera lub koniec tekstu.
_SENTENCE_RE = re.compile(r"[^.!?…]*[.!?…]+(?:\s+|$)|[^.!?…]+$")


def split_sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]


def enforce(text: str, max_sentences: int = 2) -> str:
    """Utnij do limitu zdań i zdejmij preambuły — reguły persony są twarde."""
    cleaned = _PREAMBLE_RE.sub("", text.strip())
    sentences = split_sentences(cleaned)
    return " ".join(sentences[:max_sentences]).strip()
