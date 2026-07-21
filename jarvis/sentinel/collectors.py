"""Kolektory Sentinela — WYŁĄCZNIE odczyt (E7).

Nie zabijają procesów, nie kasują, nie zmieniają zapory. Windows-only;
na innych systemach zwracają None i reguły ich nie widzą.
Źródła: Get-MpComputerStatus, Event Log (4625/7045/1102), autostart,
harmonogram zadań, Get-NetTCPConnection, hash nowych .exe → VirusTotal.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from typing import Iterable, Optional

_PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


def _powershell(command: str, timeout: int = 30) -> Optional[str]:
    if sys.platform != "win32":
        return None
    try:
        out = subprocess.run(
            _PS + [command], capture_output=True, text=True, timeout=timeout
        )
        return out.stdout if out.returncode == 0 else None
    except Exception:
        return None


def collect_defender() -> Optional[dict]:
    raw = _powershell(
        "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled,"
        "AntivirusEnabled,AntivirusSignatureLastUpdated | ConvertTo-Json"
    )
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return {
            "realtime_protection": bool(data.get("RealTimeProtectionEnabled")),
            "antivirus_enabled": bool(data.get("AntivirusEnabled")),
        }
    except ValueError:
        return None


def collect_events(ids: Iterable[int] = (4625, 7045, 1102), minutes: int = 30) -> Optional[list]:
    id_list = ",".join(str(i) for i in ids)
    raw = _powershell(
        f"Get-WinEvent -FilterHashtable @{{LogName='Security','System';"
        f"Id={id_list};StartTime=(Get-Date).AddMinutes(-{minutes})}} "
        "-ErrorAction SilentlyContinue | Select-Object Id,Message | ConvertTo-Json"
    )
    if raw is None:
        return None
    try:
        data = json.loads(raw) if raw.strip() else []
        if isinstance(data, dict):
            data = [data]
        events = []
        for e in data:
            event = {"id": int(e.get("Id", 0))}
            if event["id"] == 7045:
                msg = e.get("Message") or ""
                for line in msg.splitlines():
                    if "Service Name" in line or "Nazwa usługi" in line:
                        event["service"] = line.split(":", 1)[-1].strip()
            events.append(event)
        return events
    except (ValueError, TypeError):
        return None


def collect_autostart() -> Optional[list]:
    raw = _powershell(
        "Get-CimInstance Win32_StartupCommand | "
        "Select-Object -ExpandProperty Command"
    )
    return sorted(set(raw.split("\n"))) if raw else None


def collect_scheduled_tasks() -> Optional[list]:
    raw = _powershell(
        "Get-ScheduledTask | Where-Object State -ne 'Disabled' | "
        "Select-Object -ExpandProperty TaskName"
    )
    return sorted(set(l.strip() for l in raw.split("\n") if l.strip())) if raw else None


def collect_listen_ports() -> Optional[list]:
    raw = _powershell(
        "Get-NetTCPConnection -State Listen | "
        "Select-Object -ExpandProperty LocalPort"
    )
    if not raw:
        return None
    return sorted({int(p) for p in raw.split() if p.strip().isdigit()})


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_new_exes(watch_dirs: Iterable[str], seen_hashes: set[str]) -> list[dict]:
    """Nowe pliki .exe (hash nieznany w baseline). Sam odczyt, zero dotykania."""
    found = []
    for directory in watch_dirs:
        directory = os.path.expanduser(directory)
        if not os.path.isdir(directory):
            continue
        try:
            for name in os.listdir(directory):
                if not name.lower().endswith(".exe"):
                    continue
                path = os.path.join(directory, name)
                try:
                    digest = sha256_file(path)
                except OSError:
                    continue
                if digest not in seen_hashes:
                    found.append({"file": path, "sha256": digest})
        except OSError:
            continue
    return found


def virustotal_lookup(sha256: str, api_key: str) -> Optional[int]:
    """Liczba silników oznaczających plik; None gdy brak klucza/limitu."""
    if not api_key:
        return None
    import urllib.request

    req = urllib.request.Request(
        f"https://www.virustotal.com/api/v3/files/{sha256}",
        headers={"x-apikey": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        stats = data["data"]["attributes"]["last_analysis_stats"]
        return int(stats.get("malicious", 0)) + int(stats.get("suspicious", 0))
    except Exception:
        return None


def collect_snapshot(sources: dict, seen_hashes: set[str], vt_api_key: str = "") -> dict:
    """Pełna migawka wg włączonych źródeł z config.yaml."""
    snapshot: dict = {}
    if sources.get("defender_status", True):
        snapshot["defender"] = collect_defender()
    if sources.get("event_log_ids"):
        snapshot["events"] = collect_events(sources["event_log_ids"])
    if sources.get("autostart_diff", True):
        snapshot["autostart"] = collect_autostart()
    if sources.get("scheduled_tasks_diff", True):
        snapshot["scheduled_tasks"] = collect_scheduled_tasks()
    if sources.get("net_tcp_connections", True):
        snapshot["listen_ports"] = collect_listen_ports()
    if sources.get("new_exe_hash_virustotal", True):
        new_exes = collect_new_exes(["~/Downloads", "~/Pobrane"], seen_hashes)
        hits = []
        for exe in new_exes:
            positives = virustotal_lookup(exe["sha256"], vt_api_key)
            hits.append({**exe, "positives": positives or 0})
        snapshot["vt_hits"] = hits
    return {k: v for k, v in snapshot.items() if v is not None}
