"""Klient Ollamy. Twarda reguła: nigdy dwa modele w VRAM naraz.

`keep_alive: 300` — model sam znika z VRAM po 5 min ciszy.
KV cache q8 i flash attention to zmienne środowiskowe serwera Ollamy
(OLLAMA_KV_CACHE_TYPE, OLLAMA_FLASH_ATTENTION) — patrz CLAUDE.md.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Callable, Iterator, Optional

log = logging.getLogger("jarvis.ollama")


def _post(url: str, payload: dict, timeout: float = 300.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_stream(url: str, payload: dict, timeout: float = 300.0) -> Iterator[dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:
            line = line.strip()
            if line:
                yield json.loads(line.decode("utf-8"))


class OllamaClient:
    def __init__(
        self,
        url: str = "http://127.0.0.1:11434",
        keep_alive: int = 300,
        num_ctx: int = 8192,
        http: Optional[Callable[[str, dict], dict]] = None,
        http_stream: Optional[Callable[[str, dict], Iterator[dict]]] = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self._http = http or (lambda path, payload: _post(f"{self.url}{path}", payload))
        self._http_stream = http_stream or (
            lambda path, payload: _post_stream(f"{self.url}{path}", payload)
        )
        self.loaded: Optional[str] = None   # który model siedzi teraz w VRAM

    # --- zarządzanie VRAM ---------------------------------------------------

    def _ensure_single(self, model: str) -> None:
        """Zwalnia poprzedni model PRZED załadowaniem następnego."""
        if self.loaded and self.loaded != model:
            self.unload(self.loaded)

    def unload(self, model: str) -> None:
        try:
            self._http("/api/generate", {"model": model, "prompt": "", "keep_alive": 0})
        except Exception:
            log.warning("nie udało się wyładować %s", model, exc_info=True)
        if self.loaded == model:
            self.loaded = None

    def unload_all(self) -> None:
        """Tryb sleep/gaming: 0 MB VRAM zajęte przez Ollamę."""
        if self.loaded:
            self.unload(self.loaded)

    # --- generowanie ----------------------------------------------------------

    def _options(self) -> dict:
        return {"num_ctx": self.num_ctx}

    def generate(self, model: str, prompt: str, system: str = "") -> str:
        self._ensure_single(model)
        self.loaded = model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": self._options(),
        }
        if system:
            payload["system"] = system
        resp = self._http("/api/generate", payload)
        return (resp.get("response", "") or "").strip()

    def generate_stream(
        self, model: str, prompt: str, system: str = ""
    ) -> Iterator[str]:
        """Strumień fragmentów tekstu — do TTS streamowanego zdaniami."""
        self._ensure_single(model)
        self.loaded = model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": self._options(),
        }
        if system:
            payload["system"] = system
        for chunk in self._http_stream("/api/generate", payload):
            piece = chunk.get("response", "")
            if piece:
                yield piece
            if chunk.get("done"):
                break
