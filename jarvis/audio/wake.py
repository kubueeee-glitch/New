"""Wake word: openWakeWord (CPU, ~1% obciążenia). Jedyne, co żyje w sleep."""
from __future__ import annotations

from typing import Optional


class WakeWord:
    def __init__(self, model: str = "hey_jarvis", threshold: float = 0.5) -> None:
        self.model_name = model
        self.threshold = threshold
        self._model = None

    def _ensure(self) -> None:
        if self._model is None:
            from openwakeword.models import Model

            self._model = Model(
                wakeword_models=[self.model_name], inference_framework="onnx"
            )

    def detect(self, frame_i16) -> bool:
        """frame: np.int16 — openWakeWord buforuje wewnętrznie dowolne długości."""
        self._ensure()
        scores = self._model.predict(frame_i16)
        return any(v >= self.threshold for v in scores.values())

    def reset(self) -> None:
        if self._model is not None:
            self._model.reset()
