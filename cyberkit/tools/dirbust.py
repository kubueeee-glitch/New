#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dirbust.py - Fuzzing katalogow i plikow (CyberKit).

Funkcja:
  Dla podanego URL wysyla zapytania GET na sciezki ze slownika i raportuje
  te, ktore zwracaja interesujace kody statusu (200, 301, 302, 403, 500).
  Dziala wielowatkowo (domyslnie 10 watkow).

Wejscie:
  --url       adres bazowy (np. http://example.com)
  --wordlist  opcjonalny slownik sciezek (domyslnie tools/wordlists/dirs.txt)

Wyjscie:
  Tabela znalezionych sciezek z kodami statusu oraz raport JSON w reports/.

Przyklady:
    python tools/dirbust.py --url http://example.com
    python tools/dirbust.py --url http://example.com --threads 20
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from common import WORDLISTS_DIR, console, print_banner, save_json
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

# Kody statusu uznawane za "interesujace" (warte zaraportowania).
INTERESTING = {200, 204, 301, 302, 307, 401, 403, 500}

# Kolory dla poszczegolnych klas statusow (do tabeli).
STATUS_STYLE = {
    2: "green",   # 2xx - sukces
    3: "cyan",    # 3xx - przekierowanie
    4: "yellow",  # 4xx - blad klienta (np. 403 - ciekawe)
    5: "red",     # 5xx - blad serwera
}


def load_wordlist(path):
    """Wczytuje slownik sciezek (jedna sciezka w wierszu)."""
    with open(path, "r", encoding="utf-8") as f:
        return [
            line.strip().lstrip("/")
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def probe(base_url, path, timeout=5, verify=True):
    """
    Wysyla zapytanie GET na base_url/path.
    Zwraca slownik z wynikiem, gdy status jest interesujacy, w innym razie None.
    """
    url = f"{base_url.rstrip('/')}/{path}"
    headers = {"User-Agent": "CyberKit-DirBust/1.0"}
    try:
        resp = requests.get(
            url, timeout=timeout, allow_redirects=False,
            verify=verify, headers=headers,
        )
    except requests.exceptions.RequestException:
        return None

    if resp.status_code in INTERESTING:
        result = {
            "path": path,
            "url": url,
            "status": resp.status_code,
            "length": len(resp.content),
        }
        # Dla przekierowan zapisujemy cel (Location).
        if resp.is_redirect or "Location" in resp.headers:
            result["location"] = resp.headers.get("Location", "")
        return result
    return None


def run(base_url, wordlist_path, threads=10, timeout=5, verify=True):
    """Glowna logika: rownolegly fuzzing wszystkich sciezek ze slownika."""
    paths = load_wordlist(wordlist_path)
    console.print(
        f"[cyan]Cel:[/cyan] {base_url}  |  "
        f"[cyan]Slownik:[/cyan] {wordlist_path} ([bold]{len(paths)}[/bold] sciezek)  |  "
        f"[cyan]Watki:[/cyan] {threads}"
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
        task = progress.add_task("[cyan]Fuzzing...", total=len(paths))
        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [pool.submit(probe, base_url, p, timeout, verify) for p in paths]
            for fut in as_completed(futures):
                result = fut.result()
                if result:
                    found.append(result)
                progress.advance(task)

    found.sort(key=lambda x: (x["status"], x["path"]))
    render_table(found)

    report = {
        "tool": "dirbust",
        "target": base_url,
        "wordlist": str(wordlist_path),
        "paths_tested": len(paths),
        "found": len(found),
        "results": found,
    }
    save_json("dirbust", report)
    return report


def render_table(found):
    """Wyswietla znalezione sciezki w tabeli, kolorujac wg klasy statusu."""
    table = Table(title="DirBust - znalezione sciezki", show_lines=True)
    table.add_column("Status", style="bold")
    table.add_column("Sciezka", style="cyan")
    table.add_column("Dlugosc", style="dim", justify="right")
    table.add_column("Location", style="magenta")

    if not found:
        console.print("[yellow]Nie znaleziono zadnych sciezek.[/yellow]")
        return

    for item in found:
        style = STATUS_STYLE.get(item["status"] // 100, "white")
        table.add_row(
            f"[{style}]{item['status']}[/{style}]",
            item["path"],
            str(item["length"]),
            item.get("location", ""),
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="DirBust - wielowatkowy fuzzing katalogow i plikow."
    )
    parser.add_argument("--url", "-u", required=True, help="Adres bazowy (http://example.com).")
    parser.add_argument(
        "--wordlist", "-w",
        default=str(WORDLISTS_DIR / "dirs.txt"),
        help="Sciezka do slownika katalogow.",
    )
    parser.add_argument(
        "--threads", "-T", type=int, default=10,
        help="Liczba watkow (domyslnie 10).",
    )
    parser.add_argument(
        "--timeout", type=float, default=5,
        help="Timeout zapytania w sekundach (domyslnie 5).",
    )
    parser.add_argument(
        "--insecure", "-k", action="store_true",
        help="Nie weryfikuj certyfikatu SSL.",
    )
    args = parser.parse_args()

    print_banner("DIRBUST", "Wielowatkowy fuzzing katalogow i plikow (slownik)")

    try:
        run(
            args.url, args.wordlist,
            threads=args.threads, timeout=args.timeout, verify=not args.insecure,
        )
    except FileNotFoundError:
        console.print(f"[red]Nie znaleziono slownika: {args.wordlist}[/red]")
        console.print("[yellow]Uruchom najpierw: python install.py[/yellow]")


if __name__ == "__main__":
    main()
