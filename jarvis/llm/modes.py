"""Menedżer trybów (E2): sleep / listen / active / gaming — automatycznie.

| tryb   | co rezyduje            | VRAM       | wyzwalacz                        |
|--------|------------------------|------------|----------------------------------|
| sleep  | tylko wake word (CPU)  | 0 GB       | 5 min bezczynności               |
| listen | + VAD, STT             | 0 GB       | wykryte słowo klucz              |
| active | + model 4B lub 9B      | 2,5/6,6 GB | zapytanie wymagające LLM         |
| gaming | nic, tylko L0 regex    | 0 GB       | pełnoekranowy proces używa GPU   |

Gaming: wszystko idzie w dół, nawet jeśli w kolejce są zadania — wracają
po wyjściu z gry (scheduler.pause/resume).
"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Optional

from ..core.bus import Bus
from ..core.scheduler import Scheduler
from .ollama import OllamaClient

log = logging.getLogger("jarvis.modes")


class Mode(str, Enum):
    SLEEP = "sleep"
    LISTEN = "listen"
    ACTIVE = "active"
    GAMING = "gaming"


class ModeManager:
    def __init__(
        self,
        bus: Bus,
        ollama: OllamaClient,
        scheduler: Scheduler,
        sleep_after_s: int = 300,
        gaming_detector: Optional[Callable[[], bool]] = None,
        clock: Callable[[], float] = time.monotonic,
        tick_interval_s: float = 2.0,
    ) -> None:
        self.bus = bus
        self.ollama = ollama
        self.scheduler = scheduler
        self.sleep_after_s = sleep_after_s
        self.gaming_detector = gaming_detector
        self.clock = clock
        self.tick_interval_s = tick_interval_s
        self.mode = Mode.SLEEP
        self._last_activity = clock()

    def note_activity(self) -> None:
        self._last_activity = self.clock()

    async def set_mode(self, new: Mode, reason: str = "") -> None:
        if new is self.mode:
            return
        old, self.mode = self.mode, new
        if old is Mode.GAMING:
            self.scheduler.resume()
        if new in (Mode.SLEEP, Mode.GAMING):
            self.ollama.unload_all()      # 0 MB VRAM zajęte przez Ollamę
        if new is Mode.GAMING:
            self.scheduler.pause()        # zadania wracają po wyjściu z gry
        log.info("tryb %s → %s (%s)", old.value, new.value, reason)
        await self.bus.publish("mode.changed", {"old": old, "new": new, "reason": reason})

    async def on_wake_word(self) -> None:
        self.note_activity()
        if self.mode is Mode.SLEEP:
            await self.set_mode(Mode.LISTEN, "słowo klucz")

    async def ensure_active(self) -> None:
        """Zapytanie wymaga LLM. W gaming nie ładujemy nic — tylko L0."""
        self.note_activity()
        if self.mode is not Mode.GAMING:
            await self.set_mode(Mode.ACTIVE, "zapytanie do LLM")

    async def force_sleep(self, reason: str) -> None:
        """Watchdog: przekroczony budżet VRAM/temperatura → sen + głos."""
        await self.set_mode(Mode.SLEEP, reason)
        await self.bus.publish(
            "notify.speak", f"Schodzę do trybu uśpienia: {reason}."
        )

    async def tick(self) -> None:
        gaming = bool(self.gaming_detector and self.gaming_detector())
        if gaming and self.mode is not Mode.GAMING:
            await self.set_mode(Mode.GAMING, "pełnoekranowa gra")
            return
        if not gaming and self.mode is Mode.GAMING:
            await self.set_mode(Mode.LISTEN, "wyjście z gry")
            return
        idle = self.clock() - self._last_activity
        if self.mode in (Mode.LISTEN, Mode.ACTIVE) and idle >= self.sleep_after_s:
            await self.set_mode(Mode.SLEEP, "bezczynność")

    async def run(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(self.tick_interval_s)
