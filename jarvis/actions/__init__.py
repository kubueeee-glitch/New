"""Brama do akcji systemowych (E5) z twardą regułą E8:

Żadna akcja nie może zostać wywołana na podstawie tekstu odczytanego
z ekranu. Wyzwalaczem akcji jest wyłącznie głos użytkownika.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..vision.types import Trigger, TriggerSource

REFUSAL = (
    "Akcje wyzwala wyłącznie jawne polecenie głosowe — tekst z ekranu "
    "to dane, nie instrukcje."
)


class ActionGate:
    def __init__(self, handlers: Optional[dict[str, Callable]] = None) -> None:
        self.handlers = dict(handlers or {})
        self.log: list[tuple[str, dict]] = []

    def dispatch(self, action: str, trigger: Trigger, **kwargs):
        if not isinstance(trigger, Trigger) or trigger.source is not TriggerSource.VOICE:
            raise PermissionError(REFUSAL)
        self.log.append((action, kwargs))
        handler = self.handlers.get(action)
        return handler(**kwargs) if handler else None
