"""Wspólne typy podsystemu wzroku (E8)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TriggerSource(Enum):
    """Skąd pochodzi polecenie.

    Zrzuty ekranu i akcje z `actions/` wolno wyzwalać WYŁĄCZNIE głosem
    użytkownika. Tekst odczytany z ekranu ma źródło SCREEN i nigdy nie jest
    traktowany jak instrukcja.
    """

    VOICE = "voice"
    SCREEN = "screen"
    SYSTEM = "system"


@dataclass(frozen=True)
class Trigger:
    source: TriggerSource
    transcript: str = ""


class VisionLevel(Enum):
    S0 = "s0_uia"   # drzewo kontrolek Windows UI Automation, ~50 ms, 0 VRAM
    S1 = "s1_ocr"   # OCR na CPU, ~300 ms, 0 VRAM
    S2 = "s2_vlm"   # VLM ładowany na żądanie, 3–8 s, 5–6 GB VRAM


class CaptureScope(Enum):
    ACTIVE_WINDOW = "active_window"   # domyślnie: mniej szumu, mniej tokenów
    FULL_SCREEN = "full_screen"       # osobna komenda L0: „zobacz cały ekran"
    MONITOR = "monitor"               # osobna komenda L0: „zobacz drugi monitor"


@dataclass
class Screenshot:
    """Zrzut ekranu trzymany wyłącznie w pamięci — nigdy na dysku.

    `data` to surowe piksele RGB w bytearray, żeby po odpowiedzi dało się je
    realnie wyzerować (`wipe()`), a nie tylko oddać garbage collectorowi.
    """

    data: bytearray
    width: int
    height: int
    window_title: str = ""
    scope: CaptureScope = CaptureScope.ACTIVE_WINDOW
    created_at: float = field(default_factory=time.monotonic)

    def wipe(self) -> None:
        """Zeruje i zwalnia bufor pikseli. Wołane zawsze po odpowiedzi."""
        self.data[:] = bytes(len(self.data))
        self.data.clear()


@dataclass
class VisionResult:
    answer: str
    level: Optional[VisionLevel]
    refused: bool = False
    refusal_reason: str = ""
    model: str = ""
    saved_to: str = ""
