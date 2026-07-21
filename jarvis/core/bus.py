"""Bus zdarzeń: asyncio pub/sub. Jedyny kanał komunikacji między modułami."""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger("jarvis.bus")


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Callable) -> None:
        self._subs[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable) -> None:
        if handler in self._subs.get(topic, []):
            self._subs[topic].remove(handler)

    async def publish(self, topic: str, payload: Any = None) -> None:
        for handler in list(self._subs.get(topic, [])):
            try:
                result = handler(topic, payload)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                log.exception("handler %s dla %s", handler, topic)

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, topic: str, payload: Any = None) -> None:
        """Dla wątków audio: wrzuca publikację do pętli asyncio."""
        asyncio.run_coroutine_threadsafe(self.publish(topic, payload), loop)
