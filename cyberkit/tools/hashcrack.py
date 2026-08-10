#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hashcrack.py - Slownikowe lamanie hashy (CyberKit).

Funkcja:
  Wczytuje hash oraz slownik hasel i porownuje hash kazdego slowa z celem.
  Algorytm dobierany jest automatycznie na podstawie dlugosci hasha
  (MD5, SHA1, SHA256, SHA512) lub recznie przez --algo.

Wejscie:
  --hash      docelowy hash
  --wordlist  slownik hasel (domyslnie tools/wordlists/common.txt)

Wyjscie:
  Znalezione haslo lub informacja "not found" oraz raport JSON w reports/.

Przyklady:
    python tools/hashcrack.py --hash 5f4dcc3b5aa765d61d8327deb882cf99
    python tools/hashcrack.py --hash <sha1> --algo sha1 --wordlist rockyou.txt
"""

import argparse
import hashlib

from common import WORDLISTS_DIR, console, print_banner, save_json
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# Mapowanie dlugosci hasha (hex) na nazwe algorytmu.
LENGTH_TO_ALGO = {
    32: "md5",
    40: "sha1",
    64: "sha256",
    128: "sha512",
}

SUPPORTED = ("md5", "sha1", "sha256", "sha512")


def detect_algo(h):
    """Zwraca nazwe algorytmu na podstawie dlugosci hasha lub None."""
    return LENGTH_TO_ALGO.get(len(h.strip()))


def hash_word(word, algo):
    """Oblicza hash slowa wybranym algorytmem (kodowanie UTF-8)."""
    func = getattr(hashlib, algo)
    return func(word.encode("utf-8", errors="ignore")).hexdigest()


def load_wordlist(path):
    """Wczytuje slownik hasel (jedno haslo w wierszu)."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def run(target_hash, wordlist_path, algo=None):
    """Glowna logika: porownuje hash kazdego slowa ze slownika z celem."""
    target_hash = target_hash.strip().lower()

    if algo is None:
        algo = detect_algo(target_hash)
        if algo is None:
            console.print(
                "[red]Nie rozpoznano algorytmu po dlugosci hasha.[/red] "
                "Podaj recznie --algo (md5/sha1/sha256/sha512)."
            )
            return None
        console.print(f"[cyan]Wykryty algorytm:[/cyan] {algo.upper()}")

    words = load_wordlist(wordlist_path)
    console.print(
        f"[cyan]Slownik:[/cyan] {wordlist_path} ([bold]{len(words)}[/bold] hasel)  |  "
        f"[cyan]Algorytm:[/cyan] {algo.upper()}"
    )

    found = None
    attempts = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Lamanie...", total=len(words))
        for word in words:
            attempts += 1
            if hash_word(word, algo) == target_hash:
                found = word
                progress.advance(task)
                break
            progress.advance(task)

    if found is not None:
        console.print(f"\n[bold green][+] ZNALEZIONO![/bold green] Haslo: [bold]{found}[/bold]")
    else:
        console.print("\n[bold red][-] not found[/bold red] - hasla nie ma w slowniku.")

    report = {
        "tool": "hashcrack",
        "hash": target_hash,
        "algorithm": algo,
        "wordlist": str(wordlist_path),
        "attempts": attempts,
        "cracked": found is not None,
        "password": found,
    }
    save_json("hashcrack", report)
    return report


def main():
    parser = argparse.ArgumentParser(
        description="HashCrack - slownikowe lamanie hashy (hashlib)."
    )
    parser.add_argument("--hash", "-H", required=True, help="Docelowy hash.")
    parser.add_argument(
        "--wordlist", "-w",
        default=str(WORDLISTS_DIR / "common.txt"),
        help="Sciezka do slownika hasel.",
    )
    parser.add_argument(
        "--algo", "-a", choices=SUPPORTED, default=None,
        help="Algorytm hasha (domyslnie wykrywany z dlugosci).",
    )
    args = parser.parse_args()

    print_banner("HASHCRACK", "Slownikowe lamanie hashy MD5/SHA1/SHA256/SHA512")

    try:
        run(args.hash, args.wordlist, algo=args.algo)
    except FileNotFoundError:
        console.print(f"[red]Nie znaleziono slownika: {args.wordlist}[/red]")
        console.print("[yellow]Uruchom najpierw: python install.py[/yellow]")


if __name__ == "__main__":
    main()
