"""VAD: silero (CPU). Ramka 512 próbek / 16 kHz."""
from __future__ import annotations

from .priority import limit_torch_threads


class SileroVad:
    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000) -> None:
        self.threshold = threshold
        self.sample_rate = sample_rate
        self._model = None

    def _ensure(self) -> None:
        if self._model is None:
            limit_torch_threads(4)
            from silero_vad import load_silero_vad

            try:
                self._model = load_silero_vad(onnx=True)   # bez torcha, lżej na CPU
                self._onnx = True
            except Exception:
                self._model = load_silero_vad()
                self._onnx = False

    def is_speech(self, frame_i16) -> bool:
        self._ensure()
        import numpy as np

        audio = np.asarray(frame_i16, dtype=np.float32) / 32768.0
        if self._onnx:
            prob = float(self._model(audio[np.newaxis, :], self.sample_rate).item())
        else:
            import torch

            prob = float(self._model(torch.from_numpy(audio), self.sample_rate).item())
        return prob >= self.threshold

    def reset(self) -> None:
        if self._model is not None and hasattr(self._model, "reset_states"):
            self._model.reset_states()
