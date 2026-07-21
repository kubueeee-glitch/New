from __future__ import annotations

from datetime import datetime

_DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
_MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
           "sierpnia", "września", "października", "listopada", "grudnia"]


def run(args: dict, ctx) -> str:
    now = datetime.now()
    return (
        f"Jest {now.hour}:{now.minute:02d}, "
        f"{_DAYS[now.weekday()]}, {now.day} {_MONTHS[now.month - 1]}."
    )
