"""E8 — WZROK: „hej, zobacz to" → zrzut ekranu → pytanie o to, co widać.

Trójstopniowa ścieżka (wybór robi L1-fast na podstawie treści pytania):
S0 — drzewo kontrolek UI Automation (~50 ms, 0 VRAM),
S1 — OCR na CPU (~300 ms, 0 VRAM),
S2 — VLM ładowany na żądanie (3–8 s, 5–6 GB VRAM).
"""
from __future__ import annotations

from typing import Callable, Optional

from ..config import JarvisConfig
from .capture import ScreenCapture, encode_png, save_png
from .pipeline import VisionPipeline
from .privacy import PrivacyGuard
from .router import VisionRouter
from .s1_ocr import OcrEngine
from .s2_vlm import VlmClient
from .sanitize import build_screen_prompt, wrap_screen_content
from .types import (
    CaptureScope,
    Screenshot,
    Trigger,
    TriggerSource,
    VisionLevel,
    VisionResult,
)
from .vram import VramManager

__all__ = [
    "CaptureScope",
    "OcrEngine",
    "PrivacyGuard",
    "ScreenCapture",
    "Screenshot",
    "Trigger",
    "TriggerSource",
    "VisionLevel",
    "VisionPipeline",
    "VisionResult",
    "VisionRouter",
    "VlmClient",
    "VramManager",
    "build_pipeline",
    "build_screen_prompt",
    "encode_png",
    "save_png",
    "wrap_screen_content",
]


def build_pipeline(
    config: JarvisConfig,
    *,
    llm_answer: Callable[[str, str], str],
    speak: Callable[[str], None],
    vault_store: Optional[Callable[[str], None]] = None,
) -> VisionPipeline:
    """Składa produkcyjny pipeline E8 z konfiguracji.

    `llm_answer(system, user)` to model tekstowy z routera LLM (E1–E7),
    `speak(text)` to lokalny TTS, `vault_store(text)` zapisuje do vaulta
    wyłącznie tekstowe streszczenia.
    """
    vram = VramManager(
        ollama_url=config.vision.ollama_url,
        text_model=config.vision.text_model,
    )
    vlm = VlmClient(
        vram,
        ollama_url=config.vision.ollama_url,
        default_model=config.vision.s2.default_model,
        fast_model=config.vision.s2.fast_model,
        code_ui_model=config.vision.s2.code_ui_model,
        max_long_side=config.vision.max_long_side,
    )
    return VisionPipeline(
        capture=ScreenCapture(),
        ocr=OcrEngine(),
        vlm=vlm,
        llm_answer=llm_answer,
        speak=speak,
        guard=PrivacyGuard(config.privacy.excluded_windows),
        vault_store=vault_store,
        save_dir=config.vision.save_dir,
    )
