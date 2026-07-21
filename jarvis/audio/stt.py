"""STT: faster-whisper `small` int8 na CPU."""
from __future__ import annotations

from .priority import limit_torch_threads


class SpeechToText:
    def __init__(
        self,
        model: str = "small",
        compute_type: str = "int8",
        language: str = "pl",
        cpu_threads: int = 4,
    ) -> None:
        self.model_name = model
        self.compute_type = compute_type
        self.language = language
        self.cpu_threads = cpu_threads
        self._model = None

    def _ensure(self) -> None:
        if self._model is None:
            limit_torch_threads(self.cpu_threads)
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )

    def transcribe(self, frames) -> str:
        """frames: lista ramek np.int16 z mikrofonu."""
        self._ensure()
        import numpy as np

        audio = np.concatenate([np.asarray(f) for f in frames]).astype(np.float32)
        audio /= 32768.0
        segments, _ = self._model.transcribe(
            audio, language=self.language, beam_size=1, vad_filter=False
        )
        return " ".join(s.text.strip() for s in segments).strip()
