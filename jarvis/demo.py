"""Demo E8 bez warstwy głosowej (E1–E7 nie ma jeszcze w tym repo).

Wpisane z klawiatury pytanie gra rolę jawnej komendy głosowej użytkownika,
a `print` — rolę lokalnego TTS. Cała reszta (routing S0/S1/S2, menedżer VRAM,
prywatność, obrona przed injection) działa naprawdę.

Wymagania:
    pip install -r jarvis/requirements.txt
    ollama serve  +  pobrane modele z jarvis/config.yaml

Użycie (z katalogu głównego repo):
    python -m jarvis.demo                     # tryb interaktywny
    python -m jarvis.demo zobacz to           # jedno pytanie i koniec
"""
from __future__ import annotations

import os
import re
import sys

from .config import load_config
from .vision import CaptureScope, Trigger, TriggerSource, build_pipeline
from .vision.vram import _default_http


def make_speaker():
    """Lokalny TTS (pyttsx3 — na Windows głosy SAPI5); gdy go nie ma, print.

    Spec E8: natychmiastowe potwierdzenie głosem („patrzę") — cisza przez
    6 sekund sprawia wrażenie zawieszenia.
    """
    try:
        import pyttsx3

        engine = pyttsx3.init()

        def speak(text: str) -> None:
            print(f"🔊 {text}", flush=True)
            engine.say(text)
            engine.runAndWait()

        return speak
    except Exception:
        return lambda text: print(f"🔊 {text}", flush=True)


def make_llm_answer(ollama_url: str, model: str):
    """Model tekstowy z Ollamy jako zaślepka routera LLM z E1–E7."""

    def llm_answer(system: str, user: str) -> str:
        resp = _default_http(
            f"{ollama_url.rstrip('/')}/api/generate",
            {"model": model, "system": system, "prompt": user, "stream": False},
        )
        return (resp.get("response", "") or "").strip()

    return llm_answer


def parse_scope(question: str) -> tuple[CaptureScope, int]:
    """Namiastka komend L0: „zobacz cały ekran" / „zobacz drugi monitor"."""
    q = question.lower()
    if "cały ekran" in q or "caly ekran" in q or "cały pulpit" in q:
        return CaptureScope.FULL_SCREEN, 2
    if "monitor" in q:
        index = 2
        if "trzeci" in q:
            index = 3
        match = re.search(r"monitor\w*\s+(\d+)", q)
        if match:
            index = int(match.group(1))
        return CaptureScope.MONITOR, index
    return CaptureScope.ACTIVE_WINDOW, 2


def ask(pipeline, question: str) -> None:
    scope, monitor_index = parse_scope(question)
    result = pipeline.handle(
        question,
        Trigger(TriggerSource.VOICE, question),
        scope=scope,
        monitor_index=monitor_index,
        save_requested="zapisz to" in question.lower(),
    )
    tag = result.level.value if result.level else "odmowa"
    print(f"[{tag}] {result.answer}")
    if result.saved_to:
        print(f"(zapisano: {result.saved_to})")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    cfg = load_config(cfg_path)
    pipeline = build_pipeline(
        cfg,
        llm_answer=make_llm_answer(cfg.vision.ollama_url, cfg.vision.text_model),
        speak=make_speaker(),
    )

    if argv:
        ask(pipeline, " ".join(argv))
        return

    print(
        'Jarvis E8 — demo bez głosu. Przykłady: "zobacz to", "przeczytaj ten błąd",\n'
        '"co to za ikona", "zobacz cały ekran i streść", "zobacz to i zapisz to".\n'
        "Pusta linia kończy."
    )
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            break
        ask(pipeline, question)


if __name__ == "__main__":
    main()
