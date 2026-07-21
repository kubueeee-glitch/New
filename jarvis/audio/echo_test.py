"""Test E1: echo + pomiar opóźnienia od końca mowy do pierwszego dźwięku.

    python -m jarvis.audio.echo_test
"""
from __future__ import annotations

import threading

from ..config import default_config_path, load_config
from .loop import VoiceLoop
from .mic import Microphone
from .priority import set_low_priority
from .stt import SpeechToText
from .tts import make_tts
from .vad import SileroVad
from .wake import WakeWord


def main() -> None:
    cfg = load_config(default_config_path())
    set_low_priority()
    mic = Microphone(cfg.audio.input_device)
    latencies: list[float] = []

    def on_latency(s: float) -> None:
        latencies.append(s)
        target = cfg.persona.first_sound_target_ms
        print(f"opóźnienie: {s * 1000:.0f} ms (cel < {target} ms)")

    loop = VoiceLoop(
        frames=mic.frames(),
        wake=WakeWord(cfg.audio.wake_word.model, cfg.audio.wake_word.threshold),
        vad=SileroVad(),
        stt=SpeechToText(cfg.audio.stt.model, cfg.audio.stt.compute_type, cfg.audio.stt.language),
        tts=make_tts(cfg.audio.tts.engine, cfg.audio.tts.voice, cfg.audio.stt.language,
                     cfg.audio.output_device),
        respond=lambda text: [text],           # echo
        on_wake=lambda: print("▶ słucham"),
        on_transcript=lambda role, text: print(f"{role}: {text}"),
        on_latency=on_latency,
    )
    print("Echo test — powiedz słowo klucz i mów. Ctrl+C kończy.")
    try:
        loop.run(threading.Event())
    except KeyboardInterrupt:
        pass
    if latencies:
        print(f"średnie opóźnienie: {sum(latencies) / len(latencies) * 1000:.0f} ms")


if __name__ == "__main__":
    main()
