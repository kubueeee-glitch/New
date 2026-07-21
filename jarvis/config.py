"""Konfiguracja Jarvisa (fragment istotny dla E8)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class S2Settings:
    default_model: str = "qwen2.5vl:7b"      # dobry OCR i rozumienie zrzutów
    fast_model: str = "moondream"            # moondream2; tag w Ollamie: moondream
    code_ui_model: str = ""                  # np. InternVL 2.5 8B do kodu/UI


@dataclass
class VisionSettings:
    max_long_side: int = 1024
    ollama_url: str = "http://127.0.0.1:11434"
    text_model: str = ""                     # model tekstowy przywracany po S2
    save_dir: str = "."
    s2: S2Settings = field(default_factory=S2Settings)


@dataclass
class PrivacySettings:
    excluded_windows: list[str] = field(default_factory=list)


@dataclass
class JarvisConfig:
    vision: VisionSettings = field(default_factory=VisionSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)


def load_config(path: str = "config.yaml") -> JarvisConfig:
    cfg = JarvisConfig()
    if not os.path.exists(path):
        return cfg
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    vision = raw.get("vision") or {}
    s2 = vision.get("s2") or {}
    cfg.vision = VisionSettings(
        max_long_side=int(vision.get("max_long_side", cfg.vision.max_long_side)),
        ollama_url=str(vision.get("ollama_url", cfg.vision.ollama_url)),
        text_model=str(vision.get("text_model", cfg.vision.text_model)),
        save_dir=str(vision.get("save_dir", cfg.vision.save_dir)),
        s2=S2Settings(
            default_model=str(s2.get("default_model", "qwen2.5vl:7b")),
            fast_model=str(s2.get("fast_model", "moondream2")),
            code_ui_model=str(s2.get("code_ui_model", "")),
        ),
    )
    privacy = raw.get("privacy") or {}
    cfg.privacy = PrivacySettings(
        excluded_windows=[str(p) for p in (privacy.get("excluded_windows") or [])],
    )
    return cfg
