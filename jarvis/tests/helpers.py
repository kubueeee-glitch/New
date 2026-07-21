"""Atrapy do testów E8 — bez mss, PIL, OCR ani Ollamy."""
from __future__ import annotations

from typing import Optional

from jarvis.vision.types import CaptureScope, Screenshot
from jarvis.vision.vram import VramManager


def make_shot(title: str = "Notatnik") -> Screenshot:
    return Screenshot(
        data=bytearray(b"\x10\x20\x30" * 4),
        width=2,
        height=2,
        window_title=title,
    )


class FakeCapture:
    def __init__(self, title: str = "Notatnik") -> None:
        self.title = title
        self.grabs: list[CaptureScope] = []
        self.last_shot: Optional[Screenshot] = None

    def active_window_title(self) -> str:
        return self.title

    def grab(self, scope=CaptureScope.ACTIVE_WINDOW, monitor_index=2) -> Screenshot:
        self.grabs.append(scope)
        self.last_shot = make_shot(self.title)
        return self.last_shot


class FakeOcr:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.calls = 0

    def read(self, shot) -> str:
        self.calls += 1
        return self.text


class FakeVlm:
    """Atrapa VLM: przechodzi przez prawdziwy VramManager (fałszywe HTTP)."""

    def __init__(self, answer_text: str = "Opis obrazu.", events=None) -> None:
        self.answer_text = answer_text
        self.events = events if events is not None else []
        self.vram = VramManager(
            text_model="tekstowy",
            http=lambda url, payload: self.events.append(("http", payload)) or {},
        )
        self.calls: list[str] = []

    def answer(self, question: str, shot) -> tuple[str, str]:
        with self.vram.vlm_session("vlm-testowy"):
            self.events.append(("vlm_generate", question))
        self.calls.append(question)
        return self.answer_text, "vlm-testowy"
