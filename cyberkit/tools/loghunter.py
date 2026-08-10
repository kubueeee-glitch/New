#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loghunter.py - Analiza logow serwera WWW (CyberKit).

Funkcja:
  Parsuje plik logu (format Apache/Nginx combined lub generyczny) i szuka
  wzorcow atakow za pomoca wyrazen regularnych:
    * SQL Injection,
    * XSS,
    * LFI / Path Traversal,
    * RCE / Shellshock,
    * Brute force (wiele zadan/bledow logowania z jednego IP).

Wejscie:
  --file   sciezka do pliku logu

Wyjscie:
  Statystyki + lista alertow z numerami linii oraz raport JSON w reports/.

Przyklady:
    python tools/loghunter.py --file /var/log/apache2/access.log
    python tools/loghunter.py --file access.log --bruteforce-threshold 30
"""

import argparse
import re
from collections import Counter, defaultdict
from urllib.parse import unquote

from common import console, print_banner, save_json
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Regex dla formatu Apache/Nginx "combined".
LOG_LINE_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)[^"]*"\s+'
    r'(?P<status>\d{3})\s+(?P<size>\S+)'
)

# Sygnatury atakow: kategoria -> skompilowany regex (case-insensitive).
ATTACK_PATTERNS = {
    "SQLi": re.compile(
        r"union\s+select|information_schema|\bor\s+1\s*=\s*1\b|"
        r"'?\s*or\s*'?1'?\s*=\s*'?1|sleep\s*\(|benchmark\s*\(|"
        r"concat\s*\(|--\s|/\*|xp_cmdshell",
        re.IGNORECASE,
    ),
    "XSS": re.compile(
        r"<script|%3cscript|onerror\s*=|onload\s*=|javascript:|"
        r"<img[^>]*src|alert\s*\(|document\.cookie|<svg",
        re.IGNORECASE,
    ),
    "LFI": re.compile(
        r"\.\./|\.\.%2f|/etc/passwd|/etc/shadow|php://|file://|"
        r"boot\.ini|win\.ini|%00|/proc/self/environ",
        re.IGNORECASE,
    ),
    "RCE/Shellshock": re.compile(
        r"\(\)\s*\{\s*:;\s*\}|/bin/bash|/bin/sh|;\s*cat\s|;\s*id\b|"
        r"\bwget\s+http|\bcurl\s+http|nc\s+-e|system\s*\(",
        re.IGNORECASE,
    ),
}


def parse_line(line):
    """
    Parsuje pojedyncza linie logu. Zwraca slownik pol lub None,
    gdy linia nie pasuje do formatu combined (wtedy analiza generyczna).
    """
    match = LOG_LINE_RE.match(line)
    if match:
        return match.groupdict()
    return None


def scan_line(line, line_no, alerts, ip_stats, bf_endpoints):
    """
    Analizuje jedna linie: dopasowuje wzorce atakow i aktualizuje statystyki.
    """
    parsed = parse_line(line)
    ip = parsed["ip"] if parsed else None
    status = parsed["status"] if parsed else None
    path = parsed["path"] if parsed else line

    # Dekodujemy URL, aby wykryc zakodowane payloady (%2e%2e itd.).
    decoded = unquote(line)

    for category, pattern in ATTACK_PATTERNS.items():
        if pattern.search(decoded):
            alerts.append({
                "line_no": line_no,
                "category": category,
                "ip": ip,
                "status": status,
                "excerpt": line.strip()[:200],
            })

    # Zbieranie danych do detekcji brute force.
    if ip:
        ip_stats[ip] += 1
        # Nieudane uwierzytelnienie lub zadania do endpointow logowania.
        if status in ("401", "403") or re.search(
            r"/(login|signin|admin|wp-login|auth)", path, re.IGNORECASE
        ):
            bf_endpoints[ip] += 1


def detect_bruteforce(bf_endpoints, threshold):
    """Zwraca liste IP przekraczajacych prog zadan logowania/bledow auth."""
    return [
        {"ip": ip, "attempts": count}
        for ip, count in bf_endpoints.items()
        if count >= threshold
    ]


def run(log_path, bf_threshold=20):
    """Glowna logika: czyta plik logu linia po linii i analizuje."""
    alerts = []
    ip_stats = Counter()
    bf_endpoints = defaultdict(int)
    total = 0

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    console.print(f"[cyan]Plik logu:[/cyan] {log_path} ([bold]{len(lines)}[/bold] linii)")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Analiza logow...", total=len(lines))
        for i, line in enumerate(lines, start=1):
            total += 1
            scan_line(line, i, alerts, ip_stats, bf_endpoints)
            progress.advance(task)

    bruteforce = detect_bruteforce(bf_endpoints, bf_threshold)

    # Statystyki wg kategorii ataku.
    by_category = Counter(a["category"] for a in alerts)
    if bruteforce:
        by_category["BruteForce"] = len(bruteforce)

    render_stats(total, by_category, ip_stats, bruteforce)
    render_alerts(alerts)

    report = {
        "tool": "loghunter",
        "log_file": str(log_path),
        "total_lines": total,
        "alerts_count": len(alerts),
        "by_category": dict(by_category),
        "top_ips": ip_stats.most_common(10),
        "bruteforce": bruteforce,
        "alerts": alerts,
    }
    save_json("loghunter", report)
    return report


def render_stats(total, by_category, ip_stats, bruteforce):
    """Wyswietla podsumowanie statystyk."""
    table = Table(title="LogHunter - statystyki", show_lines=True)
    table.add_column("Kategoria", style="bold cyan")
    table.add_column("Liczba", style="yellow", justify="right")

    table.add_row("Przeanalizowane linie", str(total))
    for cat, count in by_category.items():
        table.add_row(cat, str(count))
    console.print(table)

    if bruteforce:
        console.print("\n[bold red]Podejrzenie brute force:[/bold red]")
        for item in bruteforce:
            console.print(f"  [red]{item['ip']}[/red] - {item['attempts']} prob")

    if ip_stats:
        console.print("\n[cyan]Najbardziej aktywne IP:[/cyan]")
        for ip, count in ip_stats.most_common(5):
            console.print(f"  {ip} - {count} zadan")


def render_alerts(alerts):
    """Wyswietla liste wykrytych alertow (pierwsze 30)."""
    if not alerts:
        console.print("\n[green]Nie wykryto wzorcow atakow.[/green]")
        return

    table = Table(
        title=f"LogHunter - alerty (pokazano do 30 z {len(alerts)})",
        show_lines=True,
    )
    table.add_column("Linia", style="dim", justify="right")
    table.add_column("Kategoria", style="bold red")
    table.add_column("IP", style="cyan")
    table.add_column("Fragment", style="white", no_wrap=False)

    for a in alerts[:30]:
        table.add_row(
            str(a["line_no"]),
            a["category"],
            a["ip"] or "-",
            a["excerpt"][:80],
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="LogHunter - analiza logow pod katem atakow."
    )
    parser.add_argument("--file", "-f", required=True, help="Sciezka do pliku logu.")
    parser.add_argument(
        "--bruteforce-threshold", type=int, default=20,
        help="Prog zadan logowania/bledow auth z jednego IP (domyslnie 20).",
    )
    args = parser.parse_args()

    print_banner("LOGHUNTER", "Analiza logow WWW pod katem atakow (SQLi/XSS/LFI/RCE/BF)")

    try:
        run(args.file, bf_threshold=args.bruteforce_threshold)
    except FileNotFoundError:
        console.print(f"[red]Nie znaleziono pliku: {args.file}[/red]")


if __name__ == "__main__":
    main()
