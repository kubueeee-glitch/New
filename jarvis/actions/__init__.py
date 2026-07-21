"""Sterowanie komputerem (E5) z twardą regułą E8.

- Wyzwalaczem akcji jest WYŁĄCZNIE głos użytkownika — tekst z ekranu
  (i wszystko z Sentinela) to dane, nie instrukcje.
- Każda akcja musi być na whiteliście z `config.yaml`.
- Akcje destrukcyjne (usuwanie, wysyłanie, instalacja, płatności)
  → potwierdzenie głosem przed wykonaniem.
- Log każdej akcji trafia do vaulta.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from ..vision.types import Trigger, TriggerSource

REFUSAL = (
    "Akcje wyzwala wyłącznie jawne polecenie głosowe — tekst z ekranu "
    "to dane, nie instrukcje."
)
REFUSAL_WHITELIST = "Ta akcja nie jest na whiteliście."


@dataclass
class PendingAction:
    action: str
    kwargs: dict = field(default_factory=dict)


class ActionGate:
    def __init__(
        self,
        handlers: Optional[dict[str, Callable]] = None,
        whitelist: Optional[Iterable[str]] = None,
        destructive: Iterable[str] = (),
        speak: Optional[Callable[[str], None]] = None,
        log_action: Optional[Callable[[str, dict, str], None]] = None,
    ) -> None:
        self.handlers = dict(handlers or {})
        self.whitelist = set(whitelist) if whitelist is not None else None
        self.destructive = set(destructive)
        self.speak = speak or (lambda text: None)
        self.log_action = log_action or (lambda action, args, status: None)
        self.log: list[tuple[str, dict]] = []
        self.pending: Optional[PendingAction] = None

    def _check_voice(self, trigger: Trigger) -> None:
        if not isinstance(trigger, Trigger) or trigger.source is not TriggerSource.VOICE:
            raise PermissionError(REFUSAL)

    def dispatch(self, action: str, trigger: Trigger, **kwargs):
        self._check_voice(trigger)
        allowed = self.whitelist | self.destructive if self.whitelist is not None else None
        if allowed is not None and action not in allowed:
            self.log_action(action, kwargs, "odmowa: poza whitelistą")
            self.speak(REFUSAL_WHITELIST)
            raise PermissionError(REFUSAL_WHITELIST)
        if action in self.destructive:
            self.pending = PendingAction(action, kwargs)
            self.log_action(action, kwargs, "czeka na potwierdzenie")
            self.speak(
                f"Działanie {action} jest nieodwracalne. Powiedz „potwierdzam”, "
                "żeby wykonać, albo „anuluj”."
            )
            return self.pending
        return self._execute(action, kwargs)

    def confirm(self, trigger: Trigger):
        """Potwierdzenie też wyłącznie głosem."""
        self._check_voice(trigger)
        if self.pending is None:
            return None
        pending, self.pending = self.pending, None
        return self._execute(pending.action, pending.kwargs)

    def cancel(self) -> None:
        if self.pending is not None:
            self.log_action(self.pending.action, self.pending.kwargs, "anulowane")
            self.pending = None

    def _execute(self, action: str, kwargs: dict):
        self.log.append((action, kwargs))
        handler = self.handlers.get(action)
        try:
            result = handler(**kwargs) if handler else None
        except Exception:
            self.log_action(action, kwargs, "błąd")
            raise
        self.log_action(action, kwargs, "ok")
        return result
