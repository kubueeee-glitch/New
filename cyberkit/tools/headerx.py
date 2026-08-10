#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
headerx.py - Analiza naglowkow bezpieczenstwa HTTP (CyberKit).

Funkcja:
  Pobiera naglowki odpowiedzi (requests) i sprawdza obecnosc kluczowych
  naglowkow bezpieczenstwa (HSTS, CSP, X-Frame-Options, X-XSS-Protection,
  X-Content-Type-Options, Referrer-Policy, Permissions-Policy). Na tej
  podstawie ocenia poziom ryzyka: LOW / MEDIUM / HIGH / CRITICAL.

Wejscie:
  --url   pelny adres URL (http:// lub https://)

Wyjscie:
  Kolorowa tabela naglowkow w terminalu oraz raport Markdown w reports/.

Przyklady:
    python tools/headerx.py --url https://example.com
    python tools/headerx.py --url http://localhost:8080 --insecure
"""

import argparse

import requests
from common import console, print_banner, save_markdown, timestamp
from rich.table import Table

# Definicja sprawdzanych naglowkow: klucz -> (opis, waga_ryzyka).
# Waga okresla, jak bardzo brak danego naglowka podnosi ryzyko.
SECURITY_HEADERS = {
    "Strict-Transport-Security": ("HSTS - wymusza HTTPS", 2),
    "Content-Security-Policy": ("CSP - ochrona przed XSS/injection", 2),
    "X-Frame-Options": ("Ochrona przed clickjacking", 2),
    "X-Content-Type-Options": ("Blokuje MIME-sniffing", 1),
    "X-XSS-Protection": ("Filtr XSS przegladarki (starszy)", 1),
    "Referrer-Policy": ("Kontrola naglowka Referer", 1),
    "Permissions-Policy": ("Kontrola uprawnien przegladarki", 1),
}


def fetch(url, method="GET", timeout=10, verify=True):
    """
    Pobiera odpowiedz HTTP wybrana metoda. Zwraca obiekt Response.
    W razie problemu z HEAD mozna sprobowac GET (fallback w main).
    """
    headers = {"User-Agent": "CyberKit-HeaderX/1.0"}
    return requests.request(
        method, url, timeout=timeout, verify=verify,
        allow_redirects=True, headers=headers,
    )


def assess(response):
    """
    Analizuje naglowki odpowiedzi. Zwraca krotke:
      (present, missing, risk_level, score)
    gdzie present/missing to slowniki naglowek -> opis.
    """
    resp_headers = {k.lower(): v for k, v in response.headers.items()}
    present, missing = {}, {}
    score = 0

    for header, (desc, weight) in SECURITY_HEADERS.items():
        if header.lower() in resp_headers:
            present[header] = resp_headers[header.lower()]
        else:
            missing[header] = desc
            score += weight

    # Ujawnienie wersji serwera to dodatkowy drobny wyciek informacji.
    server = resp_headers.get("server", "")
    if server and any(ch.isdigit() for ch in server):
        score += 1

    # Mapowanie sumy punktow na poziom ryzyka.
    if score == 0:
        risk = "LOW"
    elif score <= 2:
        risk = "MEDIUM"
    elif score <= 5:
        risk = "HIGH"
    else:
        risk = "CRITICAL"

    return present, missing, risk, score, server


RISK_STYLE = {
    "LOW": "bold green",
    "MEDIUM": "bold yellow",
    "HIGH": "bold red",
    "CRITICAL": "bold white on red",
}


def render(url, status, present, missing, risk, server):
    """Wyswietla wyniki analizy w terminalu."""
    console.print(f"[cyan]URL:[/cyan] {url}  |  [cyan]Status:[/cyan] {status}")
    if server:
        console.print(f"[cyan]Server:[/cyan] {server}")

    table = Table(title="HeaderX - naglowki bezpieczenstwa", show_lines=True)
    table.add_column("Naglowek", style="bold cyan")
    table.add_column("Status", style="white")
    table.add_column("Wartosc / opis", style="dim")

    for header, (desc, _) in SECURITY_HEADERS.items():
        if header in present:
            table.add_row(header, "[green]OBECNY[/green]", str(present[header])[:60])
        else:
            table.add_row(header, "[red]BRAK[/red]", desc)
    console.print(table)

    console.print(
        f"\nPoziom ryzyka: [{RISK_STYLE[risk]}] {risk} [/{RISK_STYLE[risk]}]"
    )


def build_markdown(url, status, present, missing, risk, score, server):
    """Buduje tresc raportu w formacie Markdown."""
    lines = [
        "# HeaderX - raport analizy naglowkow HTTP",
        "",
        f"- **URL:** {url}",
        f"- **Kod statusu:** {status}",
        f"- **Serwer:** {server or 'nieujawniony'}",
        f"- **Data:** {timestamp()}",
        f"- **Wynik punktowy ryzyka:** {score}",
        f"- **Poziom ryzyka:** **{risk}**",
        "",
        "## Naglowki obecne",
        "",
    ]
    if present:
        lines.append("| Naglowek | Wartosc |")
        lines.append("|----------|---------|")
        for h, v in present.items():
            lines.append(f"| {h} | `{str(v)[:100]}` |")
    else:
        lines.append("_Brak naglowkow bezpieczenstwa._")

    lines += ["", "## Naglowki brakujace", ""]
    if missing:
        lines.append("| Naglowek | Znaczenie |")
        lines.append("|----------|-----------|")
        for h, desc in missing.items():
            lines.append(f"| {h} | {desc} |")
    else:
        lines.append("_Wszystkie sprawdzane naglowki sa obecne._")

    lines += [
        "",
        "## Rekomendacje",
        "",
        "- Wdroz brakujace naglowki bezpieczenstwa wymienione powyzej.",
        "- Ukryj lub zminimalizuj naglowek `Server` (wersja oprogramowania).",
        "- Ustaw restrykcyjna polityke `Content-Security-Policy`.",
        "- Wlacz HSTS z dyrektywa `includeSubDomains` i dluzszym `max-age`.",
        "",
    ]
    return "\n".join(lines)


def run(url, insecure=False):
    """Uruchamia pelna analize dla podanego URL."""
    try:
        response = fetch(url, method="GET", verify=not insecure)
    except requests.exceptions.SSLError:
        console.print("[yellow]Blad SSL - sprobuj z flaga --insecure.[/yellow]")
        return None
    except requests.exceptions.RequestException as exc:
        console.print(f"[red]Blad polaczenia:[/red] {exc}")
        return None

    present, missing, risk, score, server = assess(response)
    render(url, response.status_code, present, missing, risk, server)

    md = build_markdown(url, response.status_code, present, missing, risk, score, server)
    save_markdown("headerx", md)

    return {"risk": risk, "score": score, "present": present, "missing": missing}


def main():
    parser = argparse.ArgumentParser(
        description="HeaderX - analiza naglowkow bezpieczenstwa HTTP."
    )
    parser.add_argument("--url", "-u", required=True, help="Adres URL do analizy.")
    parser.add_argument(
        "--insecure", "-k", action="store_true",
        help="Nie weryfikuj certyfikatu SSL.",
    )
    args = parser.parse_args()

    print_banner("HEADERX", "Analiza naglowkow bezpieczenstwa HTTP i ocena ryzyka")
    run(args.url, insecure=args.insecure)


if __name__ == "__main__":
    main()
