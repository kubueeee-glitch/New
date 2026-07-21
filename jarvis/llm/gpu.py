"""Odczyt GPU (nvidia-ml-py), watchdog i detekcja trybu gaming."""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Callable, Optional

from ..core.bus import Bus

log = logging.getLogger("jarvis.gpu")

_nvml_ready = False


def read_gpu_stats() -> Optional[dict]:
    """{'vram_used_mb', 'vram_total_mb', 'temp_c', 'power_w', 'util_pct'} albo None."""
    global _nvml_ready
    try:
        import pynvml

        if not _nvml_ready:
            pynvml.nvmlInit()
            _nvml_ready = True
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return {
            "vram_used_mb": mem.used // (1024 * 1024),
            "vram_total_mb": mem.total // (1024 * 1024),
            "temp_c": pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU),
            "power_w": pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0,
            "util_pct": util.gpu,
        }
    except Exception:
        return None


def _foreground_is_fullscreen() -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    return (
        rect.left <= 0
        and rect.top <= 0
        and rect.right - rect.left >= screen_w
        and rect.bottom - rect.top >= screen_h
    )


def make_gaming_detector(
    min_gpu_util_pct: int = 10,
    stats_reader: Callable[[], Optional[dict]] = read_gpu_stats,
    fullscreen_check: Callable[[], bool] = _foreground_is_fullscreen,
) -> Callable[[], bool]:
    """Gaming = pełnoekranowa aplikacja + niezerowe użycie GPU."""

    def detect() -> bool:
        if not fullscreen_check():
            return False
        stats = stats_reader()
        return bool(stats and stats["util_pct"] >= min_gpu_util_pct)

    return detect


class GpuWatchdog:
    """>6,8 GB VRAM albo >80°C → wymuś sleep i powiadom głosem."""

    def __init__(
        self,
        bus: Bus,
        force_sleep: Callable[[str], "asyncio.Future | object"],
        vram_limit_mb: int = 6800,
        temp_limit_c: int = 80,
        poll_interval_s: float = 5.0,
        stats_reader: Callable[[], Optional[dict]] = read_gpu_stats,
    ) -> None:
        self.bus = bus
        self.force_sleep = force_sleep
        self.vram_limit_mb = vram_limit_mb
        self.temp_limit_c = temp_limit_c
        self.poll_interval_s = poll_interval_s
        self.stats_reader = stats_reader
        self.last: Optional[dict] = None    # dla HUD

    async def check_once(self) -> None:
        stats = self.stats_reader()
        self.last = stats
        if not stats:
            return
        if stats["vram_used_mb"] > self.vram_limit_mb:
            await self.force_sleep(
                f"przekroczony budżet VRAM, {stats['vram_used_mb']} megabajtów"
            )
        elif stats["temp_c"] > self.temp_limit_c:
            await self.force_sleep(f"temperatura karty {stats['temp_c']} stopni")
        await self.bus.publish("gpu.stats", stats)

    async def run(self) -> None:
        while True:
            await self.check_once()
            await asyncio.sleep(self.poll_interval_s)
