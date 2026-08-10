#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
subsniffer.py - Enumeracja subdomen CyberKit.

Funkcja:
  Dla podanej domeny sprawdza listę popularnych subdomen ze słownika
  i próbuje rozwiązać je na adres IP (socket.gethostbyname). Istniejące
  subdomeny trafiają do raportu.

Wejście:
  --domain    domena bazowa (np. example.com)
  --wordlist  opcjonalna ścieżka do słownika (domyślnie
              tools/wordlists/subdomains.txt)

Wyjście:
  Tabela znalezionych subdomen wraz z IP oraz raport JSON w reports/.

Przykłady:
    python tools/subsniffer.py --domain example.com
    python tools/subsniffer.py --domain example.com --wordlist moj_slownik.txt
"""

import argparse
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import WORDLISTS_DIR, console, print_banner, save_json
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table


def load_wordlist(path):
    """Wczytuje słownik subdomen (jedna nazwa w wierszu, pomija komentarze)."""
    with open(path, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def resolve(subdomain, domain):
    """
    Próbuje rozwiązać pełną nazwę subdomeny na adres IP.
    Zwraca krotkę (fqdn, ip) lub None, gdy rekord DNS nie istnieje.
    """
    fqdn = f"{subdomain}.{domain}"
    try:
        ip = socket.gethostbyname(fqdn)
        return (fqdn, ip)
    except (socket.gaierror, socket.error):
        return None


def run(domain, wordlist_path, workers=50):
    """Główna logika: równolegle sprawdza wszystkie subdomeny ze słownika."""
    subs = load_wordlist(wordlist_path)
    console.print(
        f"[cyan]Domena:[/cyan] {domain}  |  "
        f"[cyan]Slownik:[/cyan] {wordlist_path} ([bold]{len(subs)}[/bold] wpisow)"
    )

    found = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Sprawdzanie DNS...", total=len(subs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(resolve, s, domain) for s in subs]
            for fut in as_completed(futures):
                result = fut.result()
                if result:
                    fqdn, ip = result
                    found.append({"subdomain": fqdn, "ip": ip})
                    console.print(f"[green][+][/green] {fqdn} -> {ip}")
                progress.advance(task)

    found.sort(key=lambda x: x["subdomain"])
    render_table(found)

    report = {
        "tool": "subsniffer",
        "domain": domain,
        "wordlist": str(wordlist_path),
        "checked": len(subs),
        "found": len(found),
        "results": found,
    }
    save_json("subsniffer", report)
    return report


def render_table(found):
    """Wyświetla znalezione subdomeny w tabeli."""
    table = Table(title="SubSniffer - znalezione subdomeny", show_lines=True)
    table.add_column("Subdomena", style="bold cyan")
    table.add_column("Adres IP", style="yellow")

    if not found:
        console.print("[yellow]Nie znaleziono zadnych subdomen.[/yellow]")
        return

    for item in found:
        table.add_row(item["subdomain"], item["ip"])
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="SubSniffer - enumeracja subdomen przez DNS."
    )
    parser.add_argument("--domain", "-d", required=True, help="Domena bazowa (example.com).")
    parser.add_argument(
        "--wordlist", "-w",
        default=str(WORDLISTS_DIR / "subdomains.txt"),
        help="Sciezka do slownika subdomen.",
    )
    parser.add_argument(
        "--threads", "-T", type=int, default=50,
        help="Liczba watkow (domyslnie 50).",
    )
    args = parser.parse_args()

    print_banner("SUBSNIFFER", "Enumeracja subdomen na podstawie slownika i DNS")

    try:
        run(args.domain, args.wordlist, workers=args.threads)
    except FileNotFoundError:
        console.print(f"[red]Nie znaleziono slownika: {args.wordlist}[/red]")
        console.print("[yellow]Uruchom najpierw: python install.py[/yellow]")


if __name__ == "__main__":
    main()
