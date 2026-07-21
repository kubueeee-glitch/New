from __future__ import annotations


def run(args: dict, ctx) -> str:
    text = (args.get("text") or "").strip()
    if not text:
        return "Nie usłyszałem treści notatki."
    ctx.vault.daily_append(f"- {text}")
    return "Zanotowane."
