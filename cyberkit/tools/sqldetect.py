#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sqldetect.py - Detektor SQL Injection (CyberKit).

Funkcja:
  Wysyla klasyczne payloady SQLi w miejsce {PAYLOAD} i porownuje odpowiedz
  z odpowiedzia bazowa (baseline). Sygnaly podatnosci:
    * komunikat bledu SQL w tresci odpowiedzi (regexy),
    * istotna zmiana dlugosci odpowiedzi wzgledem baseline,
    * zmiana kodu statusu HTTP.

Wejscie:
  --url   URL z placeholderem {PAYLOAD}, np. http://site/item?id={PAYLOAD}

Wyjscie:
  Lista potencjalnych podatnosci oraz raport JSON w reports/.

Przyklady:
    python tools/sqldetect.py --url "http://testphp.vulnweb.com/artists.php?artist={PAYLOAD}"
"""

import argparse
import re
from urllib.parse import quote

import requests
from common import console, print_banner, save_json
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Payloady testowe (klasyczne wektory SQLi).
PAYLOADS = [
    "'",
    "\"",
    "' OR '1'='1",
    "' OR '1'='1' -- ",
    "\" OR \"1\"=\"1",
    "' OR 1=1 -- ",
    "' UNION SELECT NULL -- ",
    "' UNION SELECT NULL,NULL -- ",
    "'; WAITFOR DELAY '0:0:0' -- ",
    "' AND '1'='2",
    "1' ORDER BY 1 -- ",
    "admin' -- ",
]

# Sygnatury bledow SQL charakterystyczne dla roznych silnikow bazodanowych.
SQL_ERRORS = [
    r"SQL syntax.*MySQL",
    r"Warning.*mysqli?",
    r"MySqlException",
    r"valid MySQL result",
    r"PostgreSQL.*ERROR",
    r"pg_query\(\)",
    r"pg_exec\(\)",
    r"Unclosed quotation mark after the character string",
    r"Microsoft OLE DB Provider for SQL Server",
    r"ODBC SQL Server Driver",
    r"SQLServer JDBC Driver",
    r"ORA-\d{5}",
    r"Oracle error",
    r"quoted string not properly terminated",
    r"SQLite/JDBCDriver",
    r"SQLite\.Exception",
    r"sqlite3.OperationalError",
    r"near \".*\": syntax error",
    r"You have an error in your SQL syntax",
]
SQL_ERROR_RE = re.compile("|".join(SQL_ERRORS), re.IGNORECASE)

# Prog roznicy dlugosci (w bajtach) uznawany za istotny.
LENGTH_THRESHOLD = 100


def send(url_template, value, timeout=8, verify=True):
    """Wysyla zapytanie z podana wartoscia i zwraca (status, tresc) lub (None, None)."""
    url = url_template.replace("{PAYLOAD}", quote(value))
    headers = {"User-Agent": "CyberKit-SQLDetect/1.0"}
    try:
        resp = requests.get(url, timeout=timeout, verify=verify, headers=headers)
        return resp.status_code, resp.text
    except requests.exceptions.RequestException:
        return None, None


def analyze(payload, status, body, base_status, base_len):
    """
    Porownuje odpowiedz payloadu z baseline i zwraca slownik z ocena.
    """
    signals = []
    error_match = None

    if body is not None:
        match = SQL_ERROR_RE.search(body)
        if match:
            error_match = match.group(0)
            signals.append("blad SQL w odpowiedzi")

        length_diff = abs(len(body) - base_len)
        if length_diff > LENGTH_THRESHOLD:
            signals.append(f"zmiana dlugosci ({length_diff} B)")

    if status is not None and base_status is not None and status != base_status:
        signals.append(f"zmiana statusu ({base_status}->{status})")

    return {
        "payload": payload,
        "status": status,
        "length": len(body) if body is not None else None,
        "sql_error": error_match,
        "signals": signals,
        "suspicious": bool(signals),
    }


def run(url_template, verify=True):
    """Pobiera baseline, testuje payloady i zbiera wyniki."""
    if "{PAYLOAD}" not in url_template:
        console.print("[red]URL musi zawierac placeholder {PAYLOAD}.[/red]")
        console.print('Przyklad: [dim]http://site/item?id={PAYLOAD}[/dim]')
        return None

    console.print(f"[cyan]Cel:[/cyan] {url_template}")

    # Baseline - "normalna" wartosc parametru.
    base_status, base_body = send(url_template, "1", verify=verify)
    if base_status is None:
        console.print("[red]Nie udalo sie pobrac odpowiedzi bazowej.[/red]")
        return None
    base_len = len(base_body)
    console.print(
        f"[dim]Baseline: status {base_status}, dlugosc {base_len} B[/dim]"
    )

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Testowanie payloadow...", total=len(PAYLOADS))
        for payload in PAYLOADS:
            status, body = send(url_template, payload, verify=verify)
            results.append(analyze(payload, status, body, base_status, base_len))
            progress.advance(task)

    suspicious = [r for r in results if r["suspicious"]]
    render_table(results)

    if any(r["sql_error"] for r in results):
        console.print(
            "\n[bold red][!] Wykryto komunikaty bledow SQL "
            "- wysokie prawdopodobienstwo SQL Injection![/bold red]"
        )
    elif suspicious:
        console.print(
            "\n[bold yellow][!] Wykryto anomalie w odpowiedziach "
            "- mozliwa podatnosc, wymaga weryfikacji.[/bold yellow]"
        )
    else:
        console.print("\n[green]Brak wyraznych sygnalow SQL Injection.[/green]")

    report = {
        "tool": "sqldetect",
        "target": url_template,
        "baseline": {"status": base_status, "length": base_len},
        "payloads_tested": len(PAYLOADS),
        "suspicious_count": len(suspicious),
        "results": results,
    }
    save_json("sqldetect", report)
    return report


def render_table(results):
    """Wyswietla wyniki testu w tabeli."""
    table = Table(title="SQLDetect - wyniki testu SQL Injection", show_lines=True)
    table.add_column("Payload", style="cyan")
    table.add_column("Status", style="dim", justify="right")
    table.add_column("Dlugosc", style="dim", justify="right")
    table.add_column("Sygnaly", style="yellow")

    for r in results:
        if r["sql_error"]:
            signal_style = "bold red"
        elif r["suspicious"]:
            signal_style = "yellow"
        else:
            signal_style = "dim"
        signals = ", ".join(r["signals"]) if r["signals"] else "brak"
        table.add_row(
            r["payload"],
            str(r["status"]) if r["status"] is not None else "-",
            str(r["length"]) if r["length"] is not None else "-",
            f"[{signal_style}]{signals}[/{signal_style}]",
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="SQLDetect - detektor SQL Injection."
    )
    parser.add_argument(
        "--url", "-u", required=True,
        help="URL z placeholderem {PAYLOAD}.",
    )
    parser.add_argument(
        "--insecure", "-k", action="store_true",
        help="Nie weryfikuj certyfikatu SSL.",
    )
    args = parser.parse_args()

    print_banner("SQLDETECT", "Detektor SQL Injection (bledy SQL, zmiana dlugosci/statusu)")
    run(args.url, verify=not args.insecure)


if __name__ == "__main__":
    main()
