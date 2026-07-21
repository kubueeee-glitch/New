"""Pętla głosowa (E1): mic → wake → VAD → STT → respond → TTS (zdaniami).

- Barge-in: mowa w trakcie odpowiedzi natychmiast ucisza TTS i zaczyna
  nagrywanie nowej wypowiedzi.
- Po odpowiedzi krótkie okno kontynuacji — można dopytać bez słowa klucza.
- Mierzy opóźnienie: koniec mowy → pierwszy dźwięk odpowiedzi (cel < 800 ms).

Logika jest czysta (wstrzykiwane komponenty, zero importów audio) —
testowalna bez mikrofonu.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Iterable, Optional

log = logging.getLogger("jarvis.voiceloop")

STATE_WAKE = "wake"
STATE_RECORD = "record"
STATE_SPEAK = "speak"
STATE_FOLLOWUP = "followup"


class VoiceLoop:
    def __init__(
        self,
        frames: Iterable,                      # generator ramek z mikrofonu
        wake,                                  # .detect(frame) -> bool
        vad,                                   # .is_speech(frame) -> bool
        stt,                                   # .transcribe(list[frame]) -> str
        tts,                                   # .speak_stream(sents, stop, on_first_sound)
        respond: Callable[[str], Iterable[str]],   # tekst → zdania odpowiedzi
        *,
        frame_ms: int = 32,
        silence_ms: int = 600,
        max_utterance_s: int = 15,
        followup_s: float = 6.0,
        barge_in_frames: int = 3,
        on_wake: Optional[Callable[[], None]] = None,
        on_activity: Optional[Callable[[], None]] = None,
        on_transcript: Optional[Callable[[str, str], None]] = None,  # (rola, tekst)
        on_latency: Optional[Callable[[float], None]] = None,        # sekundy
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.frames = frames
        self.wake = wake
        self.vad = vad
        self.stt = stt
        self.tts = tts
        self.respond = respond
        self.frame_ms = frame_ms
        self.silence_ms = silence_ms
        self.max_utterance_s = max_utterance_s
        self.followup_s = followup_s
        self.barge_in_frames = barge_in_frames
        self.on_wake = on_wake or (lambda: None)
        self.on_activity = on_activity or (lambda: None)
        self.on_transcript = on_transcript or (lambda role, text: None)
        self.on_latency = on_latency or (lambda s: None)
        self.clock = clock
        self.state = STATE_WAKE
        self._tts_stop = threading.Event()
        self._tts_thread: Optional[threading.Thread] = None

    # --- odpowiadanie ---------------------------------------------------------

    def _speak(self, text: str) -> None:
        t_end_speech = self.clock()
        self.on_transcript("ja", text)
        sentences = self.respond(text)         # może streamować z LLM
        self._tts_stop = threading.Event()

        def first_sound(t: float) -> None:
            self.on_latency(t - t_end_speech)

        def run() -> None:
            spoken = []

            def tap():
                for s in sentences:
                    spoken.append(s)
                    yield s

            try:
                self.tts.speak_stream(tap(), self._tts_stop, on_first_sound=first_sound)
            finally:
                if spoken:
                    self.on_transcript("jarvis", " ".join(spoken))

        self._tts_thread = threading.Thread(target=run, daemon=True)
        self._tts_thread.start()
        self.state = STATE_SPEAK

    def _tts_done(self) -> bool:
        return self._tts_thread is None or not self._tts_thread.is_alive()

    # --- pętla ----------------------------------------------------------------

    def run(self, stop: threading.Event) -> None:
        buf: list = []
        heard_speech = False
        silence = 0
        barge = 0
        followup_until = 0.0

        for frame in self.frames:
            if stop.is_set():
                self._tts_stop.set()
                return

            if self.state == STATE_WAKE:
                if self.wake.detect(frame):
                    self.on_wake()
                    buf, heard_speech, silence = [], False, 0
                    self.state = STATE_RECORD

            elif self.state == STATE_RECORD:
                buf.append(frame)
                if self.vad.is_speech(frame):
                    heard_speech = True
                    silence = 0
                    self.on_activity()
                else:
                    silence += self.frame_ms
                too_long = len(buf) * self.frame_ms >= self.max_utterance_s * 1000
                ended = heard_speech and silence >= self.silence_ms
                gave_up = not heard_speech and silence >= self.silence_ms * 6
                if ended or too_long:
                    text = self.stt.transcribe(buf)
                    buf = []
                    if text.strip():
                        self._speak(text)
                    else:
                        self.state = STATE_WAKE
                elif gave_up:
                    buf = []
                    self.state = STATE_WAKE

            elif self.state == STATE_SPEAK:
                if self.vad.is_speech(frame):
                    barge += 1
                    if barge >= self.barge_in_frames:      # barge-in
                        self._tts_stop.set()
                        buf, heard_speech, silence, barge = [frame], True, 0, 0
                        self.on_activity()
                        self.state = STATE_RECORD
                        continue
                else:
                    barge = 0
                if self._tts_done():
                    followup_until = self.clock() + self.followup_s
                    self.state = STATE_FOLLOWUP

            elif self.state == STATE_FOLLOWUP:
                if self.vad.is_speech(frame):              # dopytanie bez słowa klucza
                    buf, heard_speech, silence = [frame], True, 0
                    self.on_activity()
                    self.state = STATE_RECORD
                elif self.clock() >= followup_until:
                    self.state = STATE_WAKE
