"""Handlery akcji (Windows). Wszystkie wywoływane wyłącznie przez ActionGate."""
from __future__ import annotations

import subprocess
import sys
import webbrowser

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_PLAY_PAUSE = 0xB3


def _press_key(vk: int, times: int = 1) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)   # KEYEVENTF_KEYUP


def open_app(name: str) -> str:
    if sys.platform == "win32":
        subprocess.Popen(f'start "" "{name}"', shell=True)
    else:
        subprocess.Popen([name])
    return f"Uruchamiam {name}."


def close_app(name: str) -> str:
    import psutil

    count = 0
    needle = name.lower()
    for proc in psutil.process_iter(["name"]):
        if needle in (proc.info["name"] or "").lower():
            proc.terminate()
            count += 1
    return f"Zamknąłem {count} procesów {name}." if count else f"Nie widzę procesu {name}."


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return "Otwieram."


def volume_up() -> str:
    _press_key(VK_VOLUME_UP, times=5)
    return "Głośniej."


def volume_down() -> str:
    _press_key(VK_VOLUME_DOWN, times=5)
    return "Ciszej."


def mute() -> str:
    _press_key(VK_VOLUME_MUTE)
    return "Wyciszone."


def media_play_pause() -> str:
    _press_key(VK_MEDIA_PLAY_PAUSE)
    return ""


def build_handlers(vault) -> dict:
    """Komplet handlerów; note_add pisze przez vault (E4)."""
    return {
        "open_app": open_app,
        "close_app": close_app,
        "open_url": open_url,
        "set_volume": volume_up,          # alias z whitelisty konfiguracyjnej
        "volume_up": volume_up,
        "volume_down": volume_down,
        "mute": mute,
        "media_play_pause": media_play_pause,
        "note_add": lambda text: (vault.daily_append(f"- {text}") and "Zanotowane.")
        if text else "Nie usłyszałem treści.",
    }
