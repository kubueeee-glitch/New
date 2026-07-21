"""S0 — Windows UI Automation: drzewo kontrolek aktywnego okna.

~50 ms, 0 VRAM. Dla aplikacji natywnych dokładniejszy od OCR — czyta
prawdziwy tekst kontrolek (dialogi, pola, przyciski), nie zgaduje z pikseli.
Próbowany zawsze pierwszy na ścieżce tekstowej; zwraca None, gdy niedostępny
albo drzewo jest puste — wtedy router eskaluje do S1 (OCR).
"""
from __future__ import annotations

import sys
from typing import Optional


def read_active_window_text(max_elements: int = 400, max_depth: int = 12) -> Optional[str]:
    if sys.platform != "win32":
        return None
    try:
        import uiautomation as auto
    except Exception:
        return None

    try:
        root = auto.GetForegroundControl()
    except Exception:
        return None
    if root is None:
        return None

    lines: list[str] = []

    def walk(ctrl, depth: int) -> None:
        if len(lines) >= max_elements or depth > max_depth:
            return
        text = ""
        try:
            pattern = ctrl.GetValuePattern()
            text = (pattern.Value or "").strip()
        except Exception:
            pass
        if not text:
            try:
                text = (ctrl.Name or "").strip()
            except Exception:
                text = ""
        if text:
            try:
                kind = ctrl.ControlTypeName
            except Exception:
                kind = "Control"
            lines.append(f"{'  ' * depth}[{kind}] {text}")
        try:
            children = ctrl.GetChildren()
        except Exception:
            return
        for child in children:
            if len(lines) >= max_elements:
                return
            walk(child, depth + 1)

    try:
        walk(root, 0)
    except Exception:
        return None

    result = "\n".join(lines).strip()
    return result or None
