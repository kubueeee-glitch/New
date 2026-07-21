"""Mikrofon: strumień ramek int16 16 kHz mono (sounddevice)."""
from __future__ import annotations

import queue
from typing import Iterator, Optional

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512          # 32 ms — wspólna ramka dla VAD i wake worda
FRAME_MS = FRAME_SAMPLES * 1000 // SAMPLE_RATE


class Microphone:
    def __init__(self, device: Optional[int] = None) -> None:
        self.device = device

    def frames(self) -> Iterator["object"]:
        """Generator ramek np.int16[512]. Blokuje; przerywany przez close()."""
        import numpy as np
        import sounddevice as sd

        q: queue.Queue = queue.Queue(maxsize=64)
        self._closed = False

        def callback(indata, frames, time_info, status):
            try:
                q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass                      # lepiej zgubić ramkę niż blokować audio

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SAMPLES,
            channels=1,
            dtype="int16",
            device=self.device,
            callback=callback,
        ):
            while not self._closed:
                try:
                    yield q.get(timeout=0.5)
                except queue.Empty:
                    continue

    def close(self) -> None:
        self._closed = True
