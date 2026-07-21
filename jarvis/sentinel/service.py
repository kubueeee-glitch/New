"""Pętla Sentinela: co interwał migawka → reguły → alerty głosem + do vaulta."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Callable, Optional

from ..core.bus import Bus
from . import collectors
from .rules import evaluate, next_baseline
from .translator import to_speech


class SentinelService:
    def __init__(
        self,
        bus: Bus,
        sources: dict,
        state_path: str = "~/.jarvis/sentinel_state.json",
        vt_api_key: str = "",
        interval_s: int = 300,
        vault_log: Optional[Callable[[str], None]] = None,
        collect=collectors.collect_snapshot,
    ) -> None:
        self.bus = bus
        self.sources = sources
        self.state_path = os.path.expanduser(state_path)
        self.vt_api_key = vt_api_key
        self.interval_s = interval_s
        self.vault_log = vault_log or (lambda line: None)
        self.collect = collect
        self.baseline = self._load_baseline()

    def _load_baseline(self) -> dict:
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_baseline(self) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.baseline, f, ensure_ascii=False)

    async def scan_once(self) -> list:
        seen = set(self.baseline.get("seen_exe_hashes") or [])
        snapshot = await asyncio.to_thread(
            self.collect, self.sources, seen, self.vt_api_key
        )
        alerts = evaluate(snapshot, self.baseline)
        self.baseline = next_baseline(snapshot, self.baseline)
        self._save_baseline()
        for alert in alerts:
            spoken = to_speech(alert)
            self.vault_log(f"SENTINEL [{alert.severity}] {alert.rule}: {spoken}")
            await self.bus.publish("sentinel.alert", alert)
            await self.bus.publish("notify.speak", spoken)
        return alerts

    async def run(self) -> None:
        while True:
            try:
                await self.scan_once()
            except Exception:
                pass                     # obserwacja nie może wywrócić asystenta
            await asyncio.sleep(self.interval_s)
