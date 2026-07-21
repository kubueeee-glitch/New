"""Menedżer VRAM — krytyczne (E8).

Przejście do S2 wymaga sekwencji: zwolnij model tekstowy → załaduj VLM →
odpowiedz → przywróć model tekstowy. NIGDY oba naraz: przekroczenie VRAM
powoduje spill przez PCIe i zapaść wydajności rzędu 30× (z ~55 t/s do ~2 t/s)
— system nie zwolni, tylko praktycznie przestanie działać.

Watchdog z E2 obowiązuje bez zmian.
"""
from __future__ import annotations

import json
import urllib.request
from contextlib import contextmanager
from typing import Callable, Optional


def _default_http(url: str, payload: dict, timeout: float = 300.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class VramManager:
    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        text_model: str = "",
        http: Optional[Callable[[str, dict], dict]] = None,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.text_model = text_model
        self._http = http or _default_http
        self._vlm_active = False

    def _generate(self, model: str, keep_alive) -> None:
        # Pusty prompt: keep_alive=0 wyładowuje model, dodatni — wgrzewa go.
        self._http(
            f"{self.ollama_url}/api/generate",
            {"model": model, "prompt": "", "keep_alive": keep_alive},
        )

    def unload(self, model: str) -> None:
        self._generate(model, keep_alive=0)

    def warm(self, model: str) -> None:
        self._generate(model, keep_alive="30m")

    @contextmanager
    def vlm_session(self, vlm_model: str):
        """Jedyna legalna droga do VLM. Gwarantuje, że tekstowy i wizyjny
        model nigdy nie siedzą w VRAM jednocześnie."""
        if self._vlm_active:
            raise RuntimeError("Sesja VLM już trwa — nigdy dwa modele naraz.")
        self._vlm_active = True
        try:
            if self.text_model:
                self.unload(self.text_model)
            yield
        finally:
            try:
                self.unload(vlm_model)
            finally:
                self._vlm_active = False
                if self.text_model:
                    self.warm(self.text_model)
