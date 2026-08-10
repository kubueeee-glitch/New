#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
credleak.py - Szukacz wyciekow poswiadczen (CyberKit).

Funkcja:
  Skanuje plik tekstowy lub tresc strony WWW w poszukiwaniu wzorcow
  wrazliwych danych: klucze API (Google AIza..., Stripe sk_live/pk_live,
  AWS AKIA..., GitHub ghp_..., Slack), tokeny JWT, klucze prywatne, hasla
  w konfiguracji, adresy e-mail oraz adresy IP.

Wejscie:
  --target   sciezka do pliku LUB adres URL (http:// / https://)

Wyjscie:
  Lista znalezisk pogrupowana wg kategorii oraz raport JSON w reports/.
  Wartosci sekretow sa maskowane (widoczne tylko poczatek i koniec).

Przyklady:
    python tools/credleak.py --target config.js
    python tools/credleak.py --target https://example.com/app.js
"""

import argparse
import re

import requests
from common import console, print_banner, save_json
from rich.table import Table

# Kategoria -> (regex, czy_sekret_do_maskowania).
PATTERNS = {
    "Google API Key": (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), True),
    "Stripe Secret Key": (re.compile(r"sk_live_[0-9a-zA-Z]{16,}"), True),
    "Stripe Publishable Key": (re.compile(r"pk_live_[0-9a-zA-Z]{16,}"), True),
    "AWS Access Key": (re.compile(r"AKIA[0-9A-Z]{16}"), True),
    "GitHub Token": (re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}"), True),
    "Slack Token": (re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"), True),
    "Google OAuth Token": (re.compile(r"ya29\.[0-9A-Za-z\-_]+"), True),
    "JWT": (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), True),
    "Private Key": (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"), True),
    "Password (config)": (
        re.compile(r"""(?i)(?:password|passwd|pwd|pass)\s*[:=]\s*['"]?([^\s'";,]{4,})"""),
        True,
    ),
    "API Key (generic)": (
        re.compile(r"""(?i)(?:api[_-]?key|apikey|secret|token)\s*[:=]\s*['"]?([A-Za-z0-9\-_]{12,})"""),
        True,
    ),
    "Email": (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), False),
    "IPv4": (
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"),
        False,
    ),
}


def mask(value):
    """Maskuje srodek sekretu, pozostawiajac poczatek i koniec (do podgladu)."""
    if len(value) <= 8:
        return value[0] + "*" * (len(value) - 1)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def load_content(target):
    """
    Wczytuje tresc do przeskanowania.
    Zwraca krotke (content, source_type) gdzie source_type to 'url' lub 'file'.
    """
    if target.startswith(("http://", "https://")):
        headers = {"User-Agent": "CyberKit-CredLeak/1.0"}
        resp = requests.get(target, timeout=15, headers=headers)
        return resp.text, "url"
    with open(target, "r", encoding="utf-8", errors="ignore") as f:
        return f.read(), "file"


def scan(content):
    """
    Przeszukuje tresc wszystkimi wzorcami.
    Zwraca slownik: kategoria -> lista unikalnych znalezisk (slowniki).
    """
    findings = {}
    for category, (pattern, is_secret) in PATTERNS.items():
        seen = set()
        items = []
        for match in pattern.finditer(content):
            # Jesli regex ma grupe przechwytujaca (np. haslo), uzywamy jej.
            value = match.group(1) if match.groups() else match.group(0)
            if not value or value in seen:
                continue
            seen.add(value)
            items.append({
                "value": mask(value) if is_secret else value,
                "masked": is_secret,
            })
        if items:
            findings[category] = items
    return findings


def run(target):
    """Glowna logika: wczytuje tresc, skanuje i raportuje wyniki."""
    try:
        content, source_type = load_content(target)
    except requests.exceptions.RequestException as exc:
        console.print(f"[red]Blad pobierania URL:[/red] {exc}")
        return None
    except FileNotFoundError:
        console.print(f"[red]Nie znaleziono pliku: {target}[/red]")
        return None

    console.print(
        f"[cyan]Zrodlo:[/cyan] {target} ([bold]{source_type}[/bold], "
        f"{len(content)} znakow)"
    )

    findings = scan(content)
    render(findings)

    total = sum(len(v) for v in findings.values())
    report = {
        "tool": "credleak",
        "target": target,
        "source_type": source_type,
        "categories_found": len(findings),
        "total_findings": total,
        "findings": findings,
    }
    save_json("credleak", report)
    return report


def render(findings):
    """Wyswietla znaleziska pogrupowane wg kategorii."""
    if not findings:
        console.print("[green]Nie znaleziono wzorcow wrazliwych danych.[/green]")
        return

    table = Table(title="CredLeak - znaleziska", show_lines=True)
    table.add_column("Kategoria", style="bold red")
    table.add_column("Liczba", style="yellow", justify="right")
    table.add_column("Przyklady (maskowane)", style="cyan", no_wrap=False)

    for category, items in findings.items():
        examples = ", ".join(i["value"] for i in items[:5])
        if len(items) > 5:
            examples += f", ... (+{len(items) - 5})"
        table.add_row(category, str(len(items)), examples)
    console.print(table)

    total = sum(len(v) for v in findings.values())
    console.print(
        f"\n[bold red][!] Znaleziono {total} potencjalnych wyciekow "
        f"w {len(findings)} kategoriach.[/bold red]"
    )


def main():
    parser = argparse.ArgumentParser(
        description="CredLeak - szukacz wyciekow poswiadczen w pliku lub na stronie."
    )
    parser.add_argument(
        "--target", "-t", required=True,
        help="Sciezka do pliku lub adres URL.",
    )
    args = parser.parse_args()

    print_banner("CREDLEAK", "Szukacz wyciekow: klucze API, tokeny, hasla, emaile, IP")
    run(args.target)


if __name__ == "__main__":
    main()
