#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hashid.py - Identyfikator typu hasha (CyberKit).

Funkcja:
  Na podstawie dlugosci oraz wyrazen regularnych rozpoznaje prawdopodobny
  typ hasha: MD5, SHA1, SHA256, SHA512, bcrypt, NTLM (oraz kilka pokrewnych).
  Poniewaz rozne algorytmy daja hashe tej samej dlugosci (np. MD5 i NTLM),
  narzedzie zwraca liste WSZYSTKICH mozliwych typow.

Wejscie:
  --hash   ciag znakow hasha do identyfikacji

Wyjscie:
  Lista mozliwych typow w tabeli oraz raport JSON w reports/.

Przyklady:
    python tools/hashid.py --hash 5f4dcc3b5aa765d61d8327deb882cf99
    python tools/hashid.py --hash '$2b$12$....'
"""

import argparse
import re

from common import console, print_banner, save_json
from rich.table import Table

# Lista sygnatur: (nazwa, funkcja sprawdzajaca, dodatkowy opis).
# Kolejnosc nie ma znaczenia - zwracamy wszystkie pasujace.
HEX = re.compile(r"^[a-fA-F0-9]+$")
BCRYPT = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")
SHA_CRYPT = re.compile(r"^\$(5|6)\$")


def is_hex(value):
    """Zwraca True, gdy caly ciag sklada sie ze znakow szesnastkowych."""
    return bool(HEX.match(value))


def identify(h):
    """
    Analizuje hash i zwraca liste slownikow:
      {"type": nazwa, "confidence": poziom, "note": opis}
    posortowana od najbardziej prawdopodobnych.
    """
    h = h.strip()
    length = len(h)
    matches = []

    # Formaty z prefiksem $ maja jednoznaczna sygnature.
    if BCRYPT.match(h):
        matches.append(("bcrypt", "wysoka", "Prefiks $2a/$2b/$2y, 60 znakow"))
        return matches
    if SHA_CRYPT.match(h):
        algo = "SHA-256 crypt" if h.startswith("$5$") else "SHA-512 crypt"
        matches.append((algo, "wysoka", "Format crypt(3) z prefiksem $"))
        return matches
    if h.startswith("$1$"):
        matches.append(("MD5 crypt", "wysoka", "Format crypt(3) $1$"))
        return matches
    if h.startswith("$apr1$"):
        matches.append(("Apache MD5 (apr1)", "wysoka", "Format $apr1$"))
        return matches

    # Pozostale rozpoznajemy po dlugosci (tylko dla ciagow hex).
    if is_hex(h):
        if length == 32:
            matches.append(("MD5", "srednia", "32 znaki hex"))
            matches.append(("NTLM", "srednia", "32 znaki hex (identyczna dlugosc co MD5)"))
            matches.append(("MD4", "niska", "32 znaki hex"))
            matches.append(("LM", "niska", "32 znaki hex"))
        elif length == 40:
            matches.append(("SHA1", "srednia", "40 znakow hex"))
            matches.append(("MySQL 4.1+", "niska", "40 znakow hex (bez prefiksu *)"))
        elif length == 56:
            matches.append(("SHA-224", "srednia", "56 znakow hex"))
        elif length == 64:
            matches.append(("SHA-256", "srednia", "64 znaki hex"))
            matches.append(("SHA3-256", "niska", "64 znaki hex"))
        elif length == 96:
            matches.append(("SHA-384", "srednia", "96 znakow hex"))
        elif length == 128:
            matches.append(("SHA-512", "srednia", "128 znakow hex"))
            matches.append(("SHA3-512", "niska", "128 znakow hex"))
        elif length == 8:
            matches.append(("CRC32", "niska", "8 znakow hex"))

    # MySQL <4.1 czesto zapisywany z gwiazdka na poczatku.
    if h.startswith("*") and length == 41 and is_hex(h[1:]):
        matches.append(("MySQL 4.1+ (SHA1)", "wysoka", "Prefiks * + 40 znakow hex"))

    return matches


def run(h):
    """Uruchamia identyfikacje i wyswietla wyniki."""
    console.print(f"[cyan]Hash:[/cyan] {h}")
    console.print(f"[cyan]Dlugosc:[/cyan] {len(h.strip())} znakow\n")

    matches = identify(h)
    table = Table(title="HashID - mozliwe typy hasha", show_lines=True)
    table.add_column("Typ", style="bold cyan")
    table.add_column("Pewnosc", style="yellow")
    table.add_column("Uwagi", style="dim")

    if not matches:
        console.print("[yellow]Nie rozpoznano typu hasha (nietypowa dlugosc/format).[/yellow]")
    else:
        for name, conf, note in matches:
            table.add_row(name, conf, note)
        console.print(table)

    report = {
        "tool": "hashid",
        "hash": h.strip(),
        "length": len(h.strip()),
        "possible_types": [
            {"type": n, "confidence": c, "note": note} for n, c, note in matches
        ],
    }
    save_json("hashid", report)
    return report


def main():
    parser = argparse.ArgumentParser(
        description="HashID - identyfikacja typu hasha po dlugosci i regexach."
    )
    parser.add_argument("--hash", "-H", required=True, help="Hash do identyfikacji.")
    args = parser.parse_args()

    print_banner("HASHID", "Identyfikacja typu hasha (MD5/SHA/bcrypt/NTLM)")
    run(args.hash)


if __name__ == "__main__":
    main()
