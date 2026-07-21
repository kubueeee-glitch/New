"""Przechwytywanie ekranu (E8): biblioteka `mss`, domyślnie aktywne okno.

Aktywne okno zamiast całego pulpitu = mniej szumu, mniej tokenów obrazu,
lepsze odpowiedzi. „Zobacz cały ekran" / „zobacz drugi monitor" to osobne
komendy L0 przekładane na CaptureScope.

Zrzut nigdy nie dotyka dysku — wynik to Screenshot z pikselami w pamięci.
Zapis pliku (`save_png`) wywołuje wyłącznie pipeline i wyłącznie po jawnym
głosowym „zapisz to".
"""
from __future__ import annotations

import io
import sys
from typing import Optional

from .types import CaptureScope, Screenshot

# ~1024 px dłuższego boku przed wysłaniem do VLM — natywne 1440p to ogrom
# tokenów obrazu i kilkukrotnie dłuższy prefill.
DEFAULT_MAX_LONG_SIDE = 1024


def _active_window_rect_windows() -> tuple[Optional[dict], str]:
    """Prostokąt i tytuł aktywnego okna (tylko Windows)."""
    if sys.platform != "win32":
        return None, ""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, ""
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None, ""
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    region = {
        "left": rect.left,
        "top": rect.top,
        "width": max(1, rect.right - rect.left),
        "height": max(1, rect.bottom - rect.top),
    }
    return region, buf.value


class ScreenCapture:
    def active_window_title(self) -> str:
        _, title = _active_window_rect_windows()
        return title

    def grab(
        self,
        scope: CaptureScope = CaptureScope.ACTIVE_WINDOW,
        monitor_index: int = 2,
    ) -> Screenshot:
        import mss

        with mss.mss() as sct:
            region = None
            title = ""
            if scope is CaptureScope.ACTIVE_WINDOW:
                region, title = _active_window_rect_windows()
            if scope is CaptureScope.MONITOR:
                idx = min(max(monitor_index, 1), len(sct.monitors) - 1)
                region = sct.monitors[idx]
            if region is None:
                # cały pulpit (monitors[0] = obszar wszystkich monitorów)
                region = sct.monitors[0]
            raw = sct.grab(region)
            return Screenshot(
                data=bytearray(raw.rgb),
                width=raw.width,
                height=raw.height,
                window_title=title,
                scope=scope,
            )


def encode_png(shot: Screenshot, max_long_side: Optional[int] = DEFAULT_MAX_LONG_SIDE) -> bytes:
    """Koduje zrzut do PNG w pamięci; skaluje dłuższy bok do max_long_side.

    `max_long_side=None` = bez skalowania (używane tylko przy jawnym zapisie).
    """
    from PIL import Image

    img = Image.frombytes("RGB", (shot.width, shot.height), bytes(shot.data))
    if max_long_side:
        long_side = max(img.size)
        if long_side > max_long_side:
            scale = max_long_side / long_side
            img = img.resize(
                (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                Image.LANCZOS,
            )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def save_png(shot: Screenshot, path: str) -> str:
    """Zapis na dysk — wyłącznie ścieżka jawnego „zapisz to" w pipeline."""
    with open(path, "wb") as f:
        f.write(encode_png(shot, max_long_side=None))
    return path
