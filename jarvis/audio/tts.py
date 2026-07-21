"""TTS streamowany zdaniami + barge-in (E1).

Kokoro-82M (CPU) nie ma polskiego głosu — dla polskiego automatyczny fallback
na głosy systemowe SAPI5 (pyttsx3). Barge-in: stop_event sprawdzany co ~10 ms,
odtwarzanie milknie natychmiast.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Iterable, Optional

log = logging.getLogger("jarvis.tts")

OnFirstSound = Optional[Callable[[float], None]]


class BaseTts:
    def speak_stream(
        self, sentences: Iterable[str], stop: threading.Event, on_first_sound: OnFirstSound = None
    ) -> None:
        raise NotImplementedError


class KokoroTts(BaseTts):
    SAMPLE_RATE = 24000

    def __init__(self, voice: str = "af_heart", lang_code: str = "a",
                 output_device: Optional[int] = None) -> None:
        self.voice = voice
        self.lang_code = lang_code
        self.output_device = output_device
        self._pipeline = None

    def _ensure(self) -> None:
        if self._pipeline is None:
            from kokoro import KPipeline

            self._pipeline = KPipeline(lang_code=self.lang_code)

    def speak_stream(self, sentences, stop, on_first_sound=None) -> None:
        self._ensure()
        import sounddevice as sd

        first = True
        for sentence in sentences:
            if stop.is_set():
                break
            for _, _, audio in self._pipeline(sentence, voice=self.voice):
                if stop.is_set():
                    break
                if first and on_first_sound:
                    on_first_sound(time.monotonic())
                first = False
                sd.play(audio, self.SAMPLE_RATE, device=self.output_device)
                while True:
                    stream = sd.get_stream()
                    if stream is None or not stream.active:
                        break
                    if stop.is_set():
                        sd.stop()          # barge-in: milknij natychmiast
                        return
                    time.sleep(0.01)
        sd.stop()


class Pyttsx3Tts(BaseTts):
    """Fallback: SAPI5 na Windows (ma polskie głosy)."""

    def __init__(self, voice: str = "") -> None:
        self.voice = voice
        self._engine = None

    def _ensure(self) -> None:
        if self._engine is None:
            import pyttsx3

            self._engine = pyttsx3.init()
            if self.voice:
                for v in self._engine.getProperty("voices"):
                    if self.voice.lower() in (v.name or "").lower():
                        self._engine.setProperty("voice", v.id)
                        break

    def speak_stream(self, sentences, stop, on_first_sound=None) -> None:
        self._ensure()
        first = True
        for sentence in sentences:
            if stop.is_set():
                self._engine.stop()
                return
            if first and on_first_sound:
                on_first_sound(time.monotonic())
            first = False
            self._engine.say(sentence)
            self._engine.runAndWait()      # zdanie po zdaniu → stop między zdaniami


class NullTts(BaseTts):
    """Środowiska bez audio (testy, kontener): drukuje zamiast mówić."""

    def speak_stream(self, sentences, stop, on_first_sound=None) -> None:
        first = True
        for sentence in sentences:
            if stop.is_set():
                return
            if first and on_first_sound:
                on_first_sound(time.monotonic())
            first = False
            print(f"🔊 {sentence}", flush=True)


def make_tts(engine: str = "kokoro", voice: str = "", language: str = "pl",
             output_device: Optional[int] = None) -> BaseTts:
    if engine == "kokoro" and language != "pl":
        try:
            tts = KokoroTts(voice=voice or "af_heart", output_device=output_device)
            tts._ensure()
            return tts
        except Exception:
            log.warning("Kokoro niedostępne — fallback pyttsx3", exc_info=True)
    # polski → SAPI5; Kokoro nie wspiera pl
    try:
        tts = Pyttsx3Tts(voice=voice)
        tts._ensure()
        return tts
    except Exception:
        log.warning("pyttsx3 niedostępne — NullTts (print)", exc_info=True)
        return NullTts()
