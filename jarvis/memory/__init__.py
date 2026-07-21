"""Pamięć (E4): vault Obsidian (markdown + [[wikilinki]]) + indeks SQLite FTS5."""
from .index import MemoryIndex
from .vault import Vault

__all__ = ["MemoryIndex", "Vault"]
