"""Stan HUD-u: zbiera zdarzenia z busa, wystawia snapshot dla WebSocketu."""
from __future__ import annotations

import time
from collections import deque
from typing import Optional

from ..core.bus import Bus
from ..core.scheduler import Scheduler


class HudState:
    def __init__(self, bus: Bus, scheduler: Optional[Scheduler] = None) -> None:
        self.bus = bus
        self.scheduler = scheduler
        self.mode = "sleep"
        self.gpu: dict = {}
        self.transcript: deque = deque(maxlen=30)
        self.actions: deque = deque(maxlen=20)
        self.latency_ms: Optional[int] = None
        bus.subscribe("mode.changed", self._on_mode)
        bus.subscribe("gpu.stats", self._on_gpu)
        bus.subscribe("transcript", self._on_transcript)
        bus.subscribe("action.logged", self._on_action)
        bus.subscribe("latency", self._on_latency)

    def _on_mode(self, topic, payload) -> None:
        self.mode = getattr(payload.get("new"), "value", str(payload.get("new")))

    def _on_gpu(self, topic, payload) -> None:
        self.gpu = payload or {}

    def _on_transcript(self, topic, payload) -> None:
        self.transcript.append(
            {"role": payload["role"], "text": payload["text"],
             "t": time.strftime("%H:%M:%S")}
        )

    def _on_action(self, topic, payload) -> None:
        self.actions.append({**payload, "t": time.strftime("%H:%M:%S")})

    def _on_latency(self, topic, payload) -> None:
        self.latency_ms = int(float(payload) * 1000)

    def snapshot(self) -> dict:
        queue = []
        if self.scheduler:
            queue = [
                {"id": t.id, "name": t.name, "status": t.status, "summary": t.summary}
                for t in self.scheduler.snapshot()
            ]
        return {
            "mode": self.mode,
            "gpu": self.gpu,
            "latency_ms": self.latency_ms,
            "transcript": list(self.transcript),
            "actions": list(self.actions),
            "queue": queue,
        }
