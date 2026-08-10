#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
common.py - Wspólne funkcje pomocnicze dla wszystkich narzędzi CyberKit.

Moduł dostarcza:
  * jeden współdzielony obiekt konsoli rich (Console),
  * ścieżki do katalogów reports/ oraz tools/wordlists/,
  * generowanie znaczników czasu (timestamp) do nazw raportów,
  * zapis raportów w formatach JSON i Markdown,
  * baner ostrzegawczy wyświetlany na starcie każdego narzędzia.

Każde narzędzie w folderze tools/ importuje ten moduł: gdy uruchamiamy skrypt
przez "python tools/<narzedzie>.py", katalog tools/ trafia do sys.path[0],
więc "import common" działa poprawnie.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# --- Kontrola zależności rich -----------------------------------------------
# rich jest wymagane. Jeśli go nie ma, pokazujemy czytelną instrukcję zamiast
# nieczytelnego tracebacku.
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
except ImportError:  # pragma: no cover - obsługa braku zależności
    sys.stderr.write(
        "\n[!] Brak biblioteki 'rich'. Uruchom najpierw instalator:\n"
        "    python install.py\n"
        "lub zainstaluj ręcznie: pip install rich requests\n\n"
    )
    sys.exit(1)

# Jeden wspólny obiekt konsoli dla całego zestawu narzędzi.
console = Console()

# --- Ścieżki katalogów -------------------------------------------------------
# common.py leży w cyberkit/tools/, więc korzeń pakietu to katalog wyżej.
PKG_ROOT = Path(__file__).resolve().parent.parent          # .../cyberkit
REPORTS_DIR = PKG_ROOT / "reports"                          # .../cyberkit/reports
WORDLISTS_DIR = PKG_ROOT / "tools" / "wordlists"            # .../cyberkit/tools/wordlists

# Treść ostrzeżenia prawnego – kluczowy element etycznego narzędzia.
WARNING_TEXT = (
    "Uzywaj tylko na wlasnych systemach lub z pisemna zgoda wlasciciela.\n"
    "Nieautoryzowane skanowanie i testowanie jest nielegalne."
)


def ensure_dirs():
    """Upewnia się, że katalogi reports/ oraz wordlists/ istnieją."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    WORDLISTS_DIR.mkdir(parents=True, exist_ok=True)


def timestamp():
    """Zwraca znacznik czasu w formacie RRRRMMDD_GGMMSS – do nazw plików."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def print_warning():
    """Wyświetla baner z ostrzeżeniem prawnym (żółta ramka)."""
    console.print(
        Panel(
            Text(WARNING_TEXT, justify="center", style="bold yellow"),
            title="[bold red]OSTRZEZENIE[/bold red]",
            border_style="yellow",
        )
    )


def print_banner(name, description):
    """
    Wyświetla nagłówek pojedynczego narzędzia wraz z ostrzeżeniem.

    :param name: nazwa narzędzia (np. "NETSPIDER")
    :param description: krótki opis funkcji narzędzia
    """
    print_warning()
    console.print(
        Panel(
            Text(description, justify="center", style="cyan"),
            title=f"[bold cyan]{name}[/bold cyan]",
            border_style="cyan",
        )
    )


def save_json(prefix, data):
    """
    Zapisuje słownik/listę do pliku JSON w katalogu reports/.

    :param prefix: przedrostek nazwy pliku (np. "netspider")
    :param data: dane do zapisania (dowolna struktura serializowalna do JSON)
    :return: obiekt Path do zapisanego pliku
    """
    ensure_dirs()
    path = REPORTS_DIR / f"{prefix}_{timestamp()}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    console.print(f"[green][+][/green] Raport zapisany: [bold]{path}[/bold]")
    return path


def save_markdown(prefix, content):
    """
    Zapisuje tekst Markdown do pliku w katalogu reports/.

    :param prefix: przedrostek nazwy pliku (np. "headerx")
    :param content: gotowa treść raportu w formacie Markdown
    :return: obiekt Path do zapisanego pliku
    """
    ensure_dirs()
    path = REPORTS_DIR / f"{prefix}_{timestamp()}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    console.print(f"[green][+][/green] Raport zapisany: [bold]{path}[/bold]")
    return path
