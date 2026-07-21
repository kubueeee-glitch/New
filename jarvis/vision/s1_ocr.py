"""S1 — OCR na CPU (RapidOCR, awaryjnie PaddleOCR). ~300 ms, 0 VRAM.

Czyta każdy tekst na ekranie, także w grafice i grach. Silnik inicjalizowany
leniwie i trzymany jako singleton — pierwsze wywołanie płaci koszt startu,
kolejne już nie.
"""
from __future__ import annotations

from .types import Screenshot


class OcrEngine:
    def __init__(self) -> None:
        self._engine = None
        self._kind = ""

    def _ensure(self) -> None:
        if self._engine is not None:
            return
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
            self._kind = "rapidocr"
        except ImportError:
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(use_angle_cls=False, lang="pl", show_log=False)
            self._kind = "paddleocr"

    def read(self, shot: Screenshot) -> str:
        self._ensure()
        import numpy as np

        img = np.frombuffer(bytes(shot.data), dtype=np.uint8).reshape(
            shot.height, shot.width, 3
        )
        if self._kind == "rapidocr":
            result, _ = self._engine(img)
            lines = [item[1] for item in (result or [])]
        else:
            result = self._engine.ocr(img, cls=False)
            lines = [entry[1][0] for page in (result or []) for entry in (page or [])]
        return "\n".join(line for line in lines if line).strip()
