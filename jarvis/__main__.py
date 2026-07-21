"""Uruchomienie Jarvisa: `python -m jarvis`.

    python -m jarvis            # pełny asystent głosowy + HUD (http://127.0.0.1:8765)
    python -m jarvis --no-hud   # bez HUD-u
    python -m jarvis --text     # tryb tekstowy (bez mikrofonu — do testów na sucho)
"""
from __future__ import annotations

import argparse
import asyncio
import logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis")
    parser.add_argument("--no-hud", action="store_true", help="bez panelu HUD")
    parser.add_argument("--text", action="store_true", help="tryb tekstowy zamiast głosu")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    from .app import Jarvis

    jarvis = Jarvis()
    if args.text:
        asyncio.run(_text_repl(jarvis))
    else:
        asyncio.run(jarvis.run(with_hud=not args.no_hud))


async def _text_repl(jarvis) -> None:
    jarvis.loop = asyncio.get_running_loop()
    await jarvis.scheduler.start()
    print("Jarvis — tryb tekstowy. Wpisuj wypowiedzi jak przez mikrofon. Pusta linia kończy.")
    while True:
        try:
            text = (await asyncio.to_thread(input, "> ")).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        for sentence in await jarvis.handle_utterance(text):
            print(f"🔊 {sentence}")
    await jarvis.scheduler.stop()


if __name__ == "__main__":
    main()
