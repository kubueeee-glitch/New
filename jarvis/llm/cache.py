"""Cache odpowiedzi routera na dysku (E2). Klucz: model + system + prompt."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Optional


class DiskCache:
    def __init__(self, root: str) -> None:
        self.root = os.path.expanduser(root)

    def _path(self, model: str, system: str, prompt: str) -> str:
        digest = hashlib.sha256(
            f"{model}\x00{system}\x00{prompt}".encode("utf-8")
        ).hexdigest()
        return os.path.join(self.root, digest[:2], f"{digest}.json")

    def get(self, model: str, system: str, prompt: str) -> Optional[str]:
        path = self._path(model, system, prompt)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)["response"]
        except (OSError, ValueError, KeyError):
            return None

    def put(self, model: str, system: str, prompt: str, response: str) -> None:
        path = self._path(model, system, prompt)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"model": model, "response": response}, f, ensure_ascii=False)
