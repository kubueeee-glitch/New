"""Router L0 → L1-fast → L1-main (E2).

L0: regex, 0 tokenów, 0 ms — komendy deterministyczne.
L1-fast (qwen3:4b): routing intencji i krótkie odpowiedzi. Krótsza odpowiedź
po 400 ms bije lepszą z 9B po 4 s.
L1-main (qwen3.5:9b): rozmowa i rozumowanie, z pamięcią (recall) i historią.
L2: darmowe API — domyślnie wyłączone w configu.
"""
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from . import persona
from .cache import DiskCache
from .ollama import OllamaClient

L0_COMMANDS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bktóra\s+(jest\s+)?godzina\b|\bpodaj\s+czas\b", re.I), "time"),
    (re.compile(r"\bjaki\s+(dziś|dzisiaj|mamy)\s+dzień\b|\bjaka\s+(jest\s+)?data\b", re.I), "date"),
    (re.compile(r"\bgłośniej\b", re.I), "volume_up"),
    (re.compile(r"\bciszej\b", re.I), "volume_down"),
    (re.compile(r"\bwycisz\b|\bmute\b", re.I), "mute"),
    (re.compile(r"\b(pauza|wznów|zatrzymaj\s+muzykę|puść\s+muzykę)\b", re.I), "media_play_pause"),
    (re.compile(r"\bzapisz\s+notatkę\s+(?P<text>.+)$", re.I | re.S), "note_add"),
    (re.compile(r"\bzobacz\s+cały\s+(ekran|pulpit)\b", re.I), "vision_full_screen"),
    (re.compile(r"\bzobacz\s+(?P<ord>drugi|trzeci|\d+)\s+monitor\b", re.I), "vision_monitor"),
    (re.compile(r"\b(zobacz|spójrz\s+na)\s+(to|ekran)\b", re.I), "vision_look"),
    (re.compile(r"\b(idź\s+spać|śpij|dobranoc)\b", re.I), "sleep"),
    (re.compile(r"^\s*(stop|cisza|przestań)\s*$", re.I), "stop_speaking"),
]

_CLASSIFY_SYSTEM = (
    "Jesteś routerem intencji asystenta głosowego. Odpowiadasz WYŁĄCZNIE jednym "
    "obiektem JSON, bez żadnego innego tekstu, w formacie: "
    '{"cel": "krotka" | "rozmowa" | "skill", "skill": "<nazwa>" | null}.\n'
    "- \"krotka\": proste pytanie — fakt, obliczenie, definicja; odpowiesz jednym zdaniem.\n"
    "- \"rozmowa\": wymaga rozumowania, kontekstu rozmowy albo dłuższego namysłu.\n"
    "- \"skill\": pasuje do jednego z dostępnych skilli (podaj jego nazwę)."
)


@dataclass
class RouteResult:
    level: str                      # l0 | l1_fast | l1_main | skill
    intent: str = ""                # dla l0 / skill
    args: dict = field(default_factory=dict)
    answer: str = ""                # dla l1_*


class Router:
    def __init__(
        self,
        ollama: OllamaClient,
        l1_fast: str,
        l1_main: str,
        cache: Optional[DiskCache] = None,
        max_sentences: int = 2,
        history_len: int = 6,
    ) -> None:
        self.ollama = ollama
        self.l1_fast = l1_fast
        self.l1_main = l1_main
        self.cache = cache
        self.max_sentences = max_sentences
        # Ciągłość: pamięta poprzednie wymiany bez powtarzania kontekstu.
        self.history: deque[tuple[str, str]] = deque(maxlen=history_len)

    # --- L0 -----------------------------------------------------------------

    @staticmethod
    def match_l0(text: str) -> Optional[RouteResult]:
        for pattern, intent in L0_COMMANDS:
            m = pattern.search(text)
            if m:
                return RouteResult(level="l0", intent=intent, args=m.groupdict())
        return None

    # --- L1 -----------------------------------------------------------------

    def _cached_generate(self, model: str, prompt: str, system: str) -> str:
        if self.cache:
            hit = self.cache.get(model, system, prompt)
            if hit is not None:
                return hit
        out = self.ollama.generate(model, prompt, system=system)
        if self.cache:
            self.cache.put(model, system, prompt, out)
        return out

    def classify(self, text: str, skill_names: list[str]) -> tuple[str, str]:
        """Zwraca ("krotka"|"rozmowa"|"skill", nazwa_skilla)."""
        prompt = f"Dostępne skille: {', '.join(skill_names) or 'brak'}\nWypowiedź: {text}"
        raw = self._cached_generate(self.l1_fast, prompt, _CLASSIFY_SYSTEM)
        try:
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0)) if m else {}
        except (ValueError, AttributeError):
            data = {}
        goal = data.get("cel", "rozmowa")
        skill = data.get("skill") or ""
        if goal == "skill" and skill in skill_names:
            return "skill", skill
        if goal == "krotka":
            return "krotka", ""
        return "rozmowa", ""

    def _context_block(self, recall_fragments: list[str]) -> str:
        parts = []
        if self.history:
            dialog = "\n".join(f"Ja: {u}\nTy: {a}" for u, a in self.history)
            parts.append(f"Poprzednie wymiany:\n{dialog}")
        if recall_fragments:
            notes = "\n---\n".join(recall_fragments)
            parts.append(f"Fragmenty z pamięci (mogą pomóc):\n{notes}")
        return ("\n\n".join(parts) + "\n\n") if parts else ""

    def answer_fast(self, text: str) -> RouteResult:
        raw = self.ollama.generate(
            self.l1_fast, text, system=persona.SYSTEM_PROMPT
        )
        answer = persona.enforce(raw, self.max_sentences)
        self.history.append((text, answer))
        return RouteResult(level="l1_fast", answer=answer)

    def answer_main(self, text: str, recall_fragments: list[str] | None = None) -> RouteResult:
        prompt = self._context_block(recall_fragments or []) + f"Ja: {text}"
        raw = self.ollama.generate(self.l1_main, prompt, system=persona.SYSTEM_PROMPT)
        answer = persona.enforce(raw, self.max_sentences)
        self.history.append((text, answer))
        return RouteResult(level="l1_main", answer=answer)

    def answer_main_stream(self, text: str, recall_fragments: list[str] | None = None):
        """Strumień zdań (do TTS). Persona: ucina po limicie zdań."""
        prompt = self._context_block(recall_fragments or []) + f"Ja: {text}"
        buffer = ""
        emitted: list[str] = []
        for piece in self.ollama.generate_stream(
            self.l1_main, prompt, system=persona.SYSTEM_PROMPT
        ):
            buffer += piece
            sentences = persona.split_sentences(buffer)
            # ostatni fragment może być niedokończonym zdaniem — zostaje w buforze
            while len(sentences) > 1 and len(emitted) < self.max_sentences:
                sentence = sentences.pop(0)
                if not emitted and _PREAMBLE_ONLY.match(sentence):
                    buffer = " ".join(sentences)
                    continue
                emitted.append(sentence)
                buffer = " ".join(sentences)
                yield sentence
            if len(emitted) >= self.max_sentences:
                break
        if len(emitted) < self.max_sentences:
            leftover = persona.enforce(buffer, self.max_sentences - len(emitted))
            if leftover:
                emitted.append(leftover)
                yield leftover
        self.history.append((text, " ".join(emitted)))


_PREAMBLE_ONLY = re.compile(
    r"^(jasne|oczywiście|pewnie|świetne pytanie|dobre pytanie)[!,.:…]*$", re.I
)
