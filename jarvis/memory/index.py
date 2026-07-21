"""Indeks pamięci: SQLite FTS5. `recall(query, k)` zwraca 3–5 fragmentów,
nigdy całych plików."""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Optional

_CHUNK_CHARS = 500
_MAX_K = 5


class MemoryIndex:
    def __init__(self, db_path: str, vault_root: str) -> None:
        self.db_path = os.path.expanduser(db_path)
        self.vault_root = os.path.expanduser(vault_root)
        self._conn: Optional[sqlite3.Connection] = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS notes USING fts5(path, chunk)"
            )
        return self._conn

    @staticmethod
    def _chunks(content: str):
        buf = ""
        for para in re.split(r"\n\s*\n", content):
            para = para.strip()
            if not para:
                continue
            if len(buf) + len(para) > _CHUNK_CHARS and buf:
                yield buf
                buf = para
            else:
                buf = f"{buf}\n{para}" if buf else para
            while len(buf) > _CHUNK_CHARS * 2:      # bardzo długi akapit
                yield buf[: _CHUNK_CHARS * 2]
                buf = buf[_CHUNK_CHARS * 2:]
        if buf:
            yield buf

    def index_text(self, relpath: str, content: str) -> None:
        db = self._db()
        with db:
            db.execute("DELETE FROM notes WHERE path = ?", (relpath,))
            db.executemany(
                "INSERT INTO notes (path, chunk) VALUES (?, ?)",
                ((relpath, chunk) for chunk in self._chunks(content)),
            )

    def index_file(self, path: str) -> None:
        rel = os.path.relpath(path, self.vault_root)
        with open(path, "r", encoding="utf-8") as f:
            self.index_text(rel, f.read())

    def rebuild(self) -> int:
        count = 0
        for dirpath, _, files in os.walk(self.vault_root):
            for name in files:
                if name.endswith(".md"):
                    self.index_file(os.path.join(dirpath, name))
                    count += 1
        return count

    def recall(self, query: str, k: int = 5) -> list[str]:
        """3–5 krótkich fragmentów z plikiem źródłowym — nigdy cały plik."""
        k = max(1, min(k, _MAX_K))
        tokens = re.findall(r"\w+", query, re.UNICODE)
        if not tokens:
            return []
        # prefiks (*) łagodzi polską odmianę: „sejf" znajdzie „sejfu"
        match = " OR ".join(f'"{t}"*' for t in tokens)
        rows = self._db().execute(
            "SELECT path, snippet(notes, 1, '', '', '…', 24) FROM notes "
            "WHERE notes MATCH ? ORDER BY rank LIMIT ?",
            (match, k),
        ).fetchall()
        return [f"{snippet}  ({path})" for path, snippet in rows]
