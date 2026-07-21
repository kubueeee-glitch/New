"""Scheduler: kolejka + pula workerów (max 3). Nigdy N wywołań LLM równolegle.

Tryb gaming pauzuje pobieranie z kolejki — zadania wracają po wyjściu z gry.
Po zakończeniu zadania w tle publikuje `task.done` — stąd proaktywne raporty
głosem („skan zakończony, dwa nowe wpisy w autostarcie").
"""
from __future__ import annotations

import asyncio
import itertools
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from .bus import Bus


@dataclass
class TaskInfo:
    id: int
    name: str
    status: str = "queued"          # queued | running | done | error
    submitted_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    summary: str = ""               # krótki opis wyniku do raportu głosowego


class Scheduler:
    def __init__(self, bus: Bus, max_workers: int = 3) -> None:
        self.bus = bus
        self.max_workers = max_workers
        self._queue: asyncio.Queue = asyncio.Queue()
        self._resume = asyncio.Event()
        self._resume.set()
        self._workers: list[asyncio.Task] = []
        self._tasks: dict[int, TaskInfo] = {}
        self._ids = itertools.count(1)

    async def start(self) -> None:
        for _ in range(self.max_workers):
            self._workers.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        self._workers.clear()

    def pause(self) -> None:
        """Gaming: nic nowego nie schodzi z kolejki."""
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    async def submit(
        self, name: str, factory: Callable[[], Coroutine[Any, Any, Any]]
    ) -> TaskInfo:
        info = TaskInfo(id=next(self._ids), name=name)
        self._tasks[info.id] = info
        await self._queue.put((info, factory))
        return info

    def snapshot(self) -> list[TaskInfo]:
        return sorted(self._tasks.values(), key=lambda t: t.id)[-20:]

    async def _worker(self) -> None:
        while True:
            info, factory = await self._queue.get()
            await self._resume.wait()
            info.status = "running"
            try:
                result = await factory()
                info.status = "done"
                info.summary = str(result) if result is not None else ""
            except Exception as exc:  # noqa: BLE001 — worker nie może paść
                info.status = "error"
                info.summary = f"{type(exc).__name__}: {exc}"
            info.finished_at = time.time()
            await self.bus.publish("task.done", info)
            self._queue.task_done()
