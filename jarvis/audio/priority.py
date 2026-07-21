"""Limity zasobów audio: BELOW_NORMAL i 4 wątki torcha — audio nie zjada CPU."""
from __future__ import annotations

import logging
import sys

log = logging.getLogger("jarvis.audio")


def set_low_priority() -> None:
    try:
        import psutil

        proc = psutil.Process()
        if sys.platform == "win32":
            proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            proc.nice(5)
    except Exception:
        log.warning("nie udało się obniżyć priorytetu", exc_info=True)


def limit_torch_threads(n: int = 4) -> None:
    try:
        import torch

        torch.set_num_threads(n)
    except ImportError:
        pass
