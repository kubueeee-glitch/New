"""Reguły Sentinela — WYŁĄCZNIE deterministyczne (E7).

LLM nigdy nie ocenia „czy to zagrożenie” — dostaje gotowy alert wyłącznie
do przetłumaczenia na mowę. Defender zostaje włączony i nietknięty.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Alert:
    rule: str
    severity: str                    # info | warn | critical
    facts: dict = field(default_factory=dict)


def evaluate(snapshot: dict, baseline: dict) -> list[Alert]:
    """Czysta funkcja: (migawka, stan odniesienia) → alerty. Zero heurystyk."""
    alerts: list[Alert] = []

    defender = snapshot.get("defender") or {}
    if defender and defender.get("realtime_protection") is False:
        alerts.append(Alert("defender_realtime_off", "critical", defender))

    events = snapshot.get("events") or []
    failed_logons = [e for e in events if e.get("id") == 4625]
    if len(failed_logons) >= 5:
        alerts.append(Alert("bruteforce_logon", "warn", {"count": len(failed_logons)}))
    for e in events:
        if e.get("id") == 7045:
            alerts.append(Alert("new_service", "warn", {"service": e.get("service", "?")}))
        elif e.get("id") == 1102:
            alerts.append(Alert("log_cleared", "critical", {}))

    for key, rule, severity in (
        ("autostart", "autostart_added", "warn"),
        ("scheduled_tasks", "task_added", "warn"),
        ("listen_ports", "new_listen_port", "info"),
    ):
        current = set(snapshot.get(key) or [])
        known = set(baseline.get(key) or [])
        added = sorted(current - known)
        if added and known:                     # pierwszy przebieg = tylko baseline
            alerts.append(Alert(rule, severity, {"added": added}))

    for hit in snapshot.get("vt_hits") or []:
        if hit.get("positives", 0) > 0:
            alerts.append(
                Alert("vt_flagged", "critical",
                      {"file": hit.get("file", "?"), "positives": hit["positives"]})
            )

    return alerts


def next_baseline(snapshot: dict, baseline: dict) -> dict:
    """Nowy stan odniesienia do diffów — po ocenie bieżącej migawki."""
    out = dict(baseline)
    for key in ("autostart", "scheduled_tasks", "listen_ports"):
        if snapshot.get(key) is not None:
            out[key] = sorted(set(snapshot[key]))
    seen = set(baseline.get("seen_exe_hashes") or [])
    for hit in snapshot.get("vt_hits") or []:
        if hit.get("sha256"):
            seen.add(hit["sha256"])
    out["seen_exe_hashes"] = sorted(seen)
    return out
