"""Lazy-loading skilli (E3).

Do kontekstu L1-fast trafiają WYŁĄCZNIE frontmattery `SKILL.md` (name +
description). Pełna treść pliku i kod skilla ładują się dopiero po wyborze
skilla przez router.
"""
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SkillMeta:
    name: str
    description: str
    directory: str


def _parse_frontmatter(path: str) -> Optional[dict]:
    """Czyta tylko blok między `---` — nigdy całego pliku do kontekstu."""
    meta: dict = {}
    with open(path, "r", encoding="utf-8") as f:
        if f.readline().strip() != "---":
            return None
        for line in f:
            line = line.rstrip("\n")
            if line.strip() == "---":
                return meta
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
    return None


class SkillRegistry:
    def __init__(self, root: Optional[str] = None) -> None:
        self.root = root or os.path.dirname(os.path.abspath(__file__))
        self._metas: Optional[list[SkillMeta]] = None

    def frontmatters(self) -> list[SkillMeta]:
        if self._metas is None:
            metas = []
            for entry in sorted(os.listdir(self.root)):
                path = os.path.join(self.root, entry, "SKILL.md")
                if os.path.isfile(path):
                    meta = _parse_frontmatter(path)
                    if meta and meta.get("name"):
                        metas.append(
                            SkillMeta(
                                name=meta["name"],
                                description=meta.get("description", ""),
                                directory=os.path.join(self.root, entry),
                            )
                        )
            self._metas = metas
        return self._metas

    def names(self) -> list[str]:
        return [m.name for m in self.frontmatters()]

    def load_full(self, name: str) -> str:
        """Pełny SKILL.md — dopiero po wyborze skilla."""
        meta = self._by_name(name)
        with open(os.path.join(meta.directory, "SKILL.md"), "r", encoding="utf-8") as f:
            return f.read()

    def run(self, name: str, args: dict, ctx: Any) -> str:
        """Import kodu skilla dopiero przy pierwszym użyciu."""
        meta = self._by_name(name)
        module = importlib.import_module(
            f"jarvis.skills.{os.path.basename(meta.directory)}.skill"
        )
        return module.run(args, ctx)

    def _by_name(self, name: str) -> SkillMeta:
        for meta in self.frontmatters():
            if meta.name == name:
                return meta
        raise KeyError(f"nieznany skill: {name}")
