"""Vault Obsidian: każda interakcja → .md z frontmatterem i wikilinkami.

Do vaulta trafia wyłącznie tekst (twarda reguła E8: nigdy obrazy).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional


class Vault:
    def __init__(self, root: str) -> None:
        self.root = os.path.expanduser(root)

    def _write(self, relpath: str, content: str, append: bool = False) -> str:
        path = os.path.join(self.root, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a" if append else "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def daily_path(self, when: Optional[datetime] = None) -> str:
        when = when or datetime.now()
        return os.path.join("daily", when.strftime("%Y-%m-%d") + ".md")

    def daily_append(self, line: str, when: Optional[datetime] = None) -> str:
        when = when or datetime.now()
        rel = self.daily_path(when)
        full = os.path.join(self.root, rel)
        if not os.path.exists(full):
            self._write(rel, f"# {when.strftime('%Y-%m-%d')}\n\n")
        return self._write(rel, line.rstrip("\n") + "\n", append=True)

    def note_interaction(
        self,
        user_text: str,
        answer: str,
        level: str = "",
        when: Optional[datetime] = None,
    ) -> str:
        when = when or datetime.now()
        day = when.strftime("%Y-%m-%d")
        rel = os.path.join(
            "interakcje", when.strftime("%Y"), when.strftime("%m"),
            when.strftime("%Y%m%d-%H%M%S") + ".md",
        )
        content = (
            "---\n"
            f"created: {when.isoformat(timespec='seconds')}\n"
            "type: interakcja\n"
            f"level: {level or 'l1'}\n"
            "---\n"
            f"Dzień: [[{day}]]\n\n"
            f"**Ja:** {user_text}\n\n"
            f"**Jarvis:** {answer}\n"
        )
        path = self._write(rel, content)
        self.daily_append(
            f"- {when.strftime('%H:%M')} — {user_text} → {answer}", when
        )
        return path

    def log_action(self, action: str, args: dict, status: str,
                   when: Optional[datetime] = None) -> str:
        """E5: log każdej akcji do vaulta."""
        when = when or datetime.now()
        rendered = " ".join(f"{k}={v}" for k, v in args.items()) if args else ""
        return self.daily_append(
            f"- {when.strftime('%H:%M')} — AKCJA `{action}` {rendered} [{status}]",
            when,
        )
