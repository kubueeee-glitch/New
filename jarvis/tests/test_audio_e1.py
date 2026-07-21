import threading
import time
import unittest

from jarvis.audio.loop import STATE_WAKE, VoiceLoop


class FakeWake:
    def __init__(self, hits):
        self.hits = set(hits)
        self.i = -1

    def detect(self, frame):
        self.i += 1
        return self.i in self.hits


class FakeVad:
    def is_speech(self, frame):
        return frame == "S"          # ramka "S" = mowa, "." = cisza


class FakeStt:
    def __init__(self, text="która godzina"):
        self.text = text
        self.calls = []

    def transcribe(self, frames):
        self.calls.append(list(frames))
        return self.text


class FakeTts:
    def __init__(self, chew_ms=0):
        self.spoken = []
        self.stopped = False
        self.chew_ms = chew_ms

    def speak_stream(self, sentences, stop, on_first_sound=None):
        first = True
        for s in sentences:
            if stop.is_set():
                self.stopped = True
                return
            if first and on_first_sound:
                on_first_sound(time.monotonic())
            first = False
            self.spoken.append(s)
            deadline = time.monotonic() + self.chew_ms / 1000
            while time.monotonic() < deadline:
                if stop.is_set():
                    self.stopped = True
                    return
                time.sleep(0.001)


def run_loop(frames, wake_hits=(0,), stt_text="która godzina", chew_ms=0,
             respond=None, silence_ms=64, followup_s=0.0):
    wake = FakeWake(wake_hits)
    stt = FakeStt(stt_text)
    tts = FakeTts(chew_ms)
    transcript, latencies = [], []
    loop = VoiceLoop(
        frames=iter(frames),
        wake=wake,
        vad=FakeVad(),
        stt=stt,
        tts=tts,
        respond=respond or (lambda text: [f"Echo: {text}"]),
        frame_ms=32,
        silence_ms=silence_ms,
        followup_s=followup_s,
        barge_in_frames=2,
        on_transcript=lambda role, text: transcript.append((role, text)),
        on_latency=latencies.append,
    )
    loop.run(threading.Event())
    if loop._tts_thread:
        loop._tts_thread.join(timeout=2)
    return loop, stt, tts, transcript, latencies


class VoiceLoopTest(unittest.TestCase):
    def test_pelny_cykl_wake_nagranie_odpowiedz(self):
        # ramka 0: wake; potem mowa i cisza 2 ramki (64 ms) → koniec wypowiedzi
        frames = ["w", "S", "S", "S", ".", ".", ".", ".", "."]
        loop, stt, tts, transcript, latencies = run_loop(frames)
        self.assertEqual(len(stt.calls), 1)
        self.assertEqual(tts.spoken, ["Echo: która godzina"])
        self.assertIn(("ja", "która godzina"), transcript)
        self.assertEqual(len(latencies), 1)   # zmierzone opóźnienie do 1. dźwięku

    def test_barge_in_ucisza_tts(self):
        # TTS długo mówi; w trakcie 2 ramki mowy → stop + nowe nagranie
        frames = ["w", "S", "S", ".", ".", "S", "S", "S", ".", ".", ".", "."]
        loop, stt, tts, transcript, _ = run_loop(frames, chew_ms=400)
        self.assertTrue(tts.stopped)          # zamilkł w pół zdania
        self.assertGreaterEqual(len(stt.calls), 2)  # nowa wypowiedź nagrana

    def test_pusta_transkrypcja_wraca_do_wake(self):
        frames = ["w", "S", ".", ".", ".", "x", "x"]
        loop, stt, tts, transcript, _ = run_loop(frames, stt_text="  ")
        self.assertEqual(tts.spoken, [])
        self.assertEqual(loop.state, STATE_WAKE)

    def test_cisza_bez_mowy_poddaje_sie(self):
        # wake, potem sama cisza (6 × silence_ms) → powrót do wake, zero STT
        frames = ["w"] + ["."] * 15
        loop, stt, tts, transcript, _ = run_loop(frames)
        self.assertEqual(stt.calls, [])
        self.assertEqual(loop.state, STATE_WAKE)

    def test_odpowiedz_streamowana_zdaniami(self):
        frames = ["w", "S", "S", ".", ".", ".", ".", "."]
        loop, stt, tts, transcript, _ = run_loop(
            frames, respond=lambda t: iter(["Pierwsze.", "Drugie."])
        )
        self.assertEqual(tts.spoken, ["Pierwsze.", "Drugie."])
        self.assertIn(("jarvis", "Pierwsze. Drugie."), transcript)


if __name__ == "__main__":
    unittest.main()
