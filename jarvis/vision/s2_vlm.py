"""S2 — VLM ładowany na żądanie (pull na żądanie, nie na starcie). 3–8 s, 5–6 GB.

Modele:
- qwen2.5vl:7b (Q4) — domyślny, dobry OCR i rozumienie zrzutów,
- InternVL 2.5 8B — wyraźnie lepszy przy zrzutach kodu i interfejsów
  (trenowany m.in. na screenshotach z GitHuba i mockupach UI),
- moondream2 (1,9 B, ~2 GB) — szybki poziom pośredni do prostych pytań.

Świadomość ograniczeń: lokalne VLM-y to klasa „solidne drugie miejsce" —
przy gęstym tekście router preferuje S1 (OCR), nie S2.
"""
from __future__ import annotations

import base64
import re
from typing import Callable, Optional

from .capture import DEFAULT_MAX_LONG_SIDE, encode_png
from .sanitize import SCREEN_DATA_SYSTEM_INSTRUCTION
from .types import Screenshot
from .vram import VramManager, _default_http

# Pytania o kod/interfejs → InternVL, o ile skonfigurowany.
CODE_UI_HINTS = ("kod", "interfejs", "mockup", "układ", "layout", "ui")
# Krótkie, proste pytania („co to za ikona") → moondream2.
SIMPLE_MAX_WORDS = 6

VLM_SYSTEM = (
    SCREEN_DATA_SYSTEM_INSTRUCTION
    + " Obraz to zrzut ekranu użytkownika — opisz go rzeczowo i po polsku."
)


class VlmClient:
    def __init__(
        self,
        vram: VramManager,
        ollama_url: str = "http://127.0.0.1:11434",
        default_model: str = "qwen2.5vl:7b",
        fast_model: str = "moondream2",
        code_ui_model: str = "",
        max_long_side: int = DEFAULT_MAX_LONG_SIDE,
        http: Optional[Callable[[str, dict], dict]] = None,
        encoder: Callable[..., bytes] = encode_png,
    ) -> None:
        self.vram = vram
        self.ollama_url = ollama_url.rstrip("/")
        self.default_model = default_model
        self.fast_model = fast_model
        self.code_ui_model = code_ui_model
        self.max_long_side = max_long_side
        self._http = http or _default_http
        self._encoder = encoder

    def pick_model(self, question: str) -> str:
        # Dopasowanie po początkach słów — radzi sobie z polską odmianą
        # („kodzie", „układzie"), a „ui" nie łapie się w środku innych słów.
        words = re.findall(r"\w+", question.lower())
        if self.code_ui_model and any(
            w.startswith(h) for w in words for h in CODE_UI_HINTS
        ):
            return self.code_ui_model
        if self.fast_model and len(words) <= SIMPLE_MAX_WORDS:
            return self.fast_model
        return self.default_model

    def _model_available(self, model: str) -> bool:
        try:
            self._http(f"{self.ollama_url}/api/show", {"model": model})
            return True
        except Exception:
            return False

    def ensure_model(self, model: str) -> None:
        """Pull na żądanie, nie na starcie — VLM dociąga się przy pierwszym
        użyciu. Wołane PRZED sesją VRAM: pobieranie to dysk i sieć, nie VRAM,
        więc model tekstowy może jeszcze spokojnie siedzieć w karcie."""
        if not self._model_available(model):
            self._http(
                f"{self.ollama_url}/api/pull", {"model": model, "stream": False}
            )

    def answer(self, question: str, shot: Screenshot) -> tuple[str, str]:
        """Zwraca (odpowiedź, użyty model). Obraz skalowany przed wysłaniem."""
        model = self.pick_model(question)
        self.ensure_model(model)
        png = self._encoder(shot, max_long_side=self.max_long_side)
        image_b64 = base64.b64encode(png).decode("ascii")
        with self.vram.vlm_session(model):
            resp = self._http(
                f"{self.ollama_url}/api/generate",
                {
                    "model": model,
                    "system": VLM_SYSTEM,
                    "prompt": question,
                    "images": [image_b64],
                    "stream": False,
                },
            )
        return (resp.get("response", "") or "").strip(), model
