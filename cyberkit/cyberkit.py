#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cyberkit.py - Menu glowne zestawu CyberKit.

Uruchamia interaktywne menu z 10 narzedziami do etycznego testowania
bezpieczenstwa. Kazde narzedzie jest osobnym skryptem w katalogu tools/
i wywolywane jest jako oddzielny proces (mozna je tez uruchamiac samodzielnie).

Uruchomienie:
    python cyberkit.py

Wymagania: rich, requests (patrz install.py).
"""

import subprocess
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    sys.stderr.write(
        "\n[!] Brak biblioteki 'rich'. Uruchom najpierw: python install.py\n\n"
    )
    sys.exit(1)

console = Console()

PKG_ROOT = Path(__file__).resolve().parent
TOOLS_DIR = PKG_ROOT / "tools"

# Uproszczona, 5-wierszowa czcionka blokowa dla liter slowa CYBERKIT.
# Dzieki generowaniu programowemu baner zawsze jest idealnie wyrownany.
_FONT = {
    "C": ["█████", "█    ", "█    ", "█    ", "█████"],
    "Y": ["█   █", "█   █", " ███ ", "  █  ", "  █  "],
    "B": ["████ ", "█   █", "████ ", "█   █", "████ "],
    "E": ["█████", "█    ", "███  ", "█    ", "█████"],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "K": ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
}


def ascii_banner(word="CYBERKIT"):
    """Buduje wielowierszowy napis ASCII dla podanego slowa."""
    rows = []
    for r in range(5):
        rows.append("  ".join(_FONT[ch][r] for ch in word if ch in _FONT))
    return "\n".join(rows)


# Rejestr narzedzi: (nazwa, skrypt, opis, flaga_arg, tekst_pytania).
TOOLS = [
    ("NetSpider", "netspider.py", "Skaner sieci: ping sweep + TCP scan top 100 portow",
     "--target", "Podaj IP lub zakres (np. 192.168.1.1-254)"),
    ("SubSniffer", "subsniffer.py", "Enumeracja subdomen przez DNS",
     "--domain", "Podaj domene (np. example.com)"),
    ("HeaderX", "headerx.py", "Analiza naglowkow bezpieczenstwa HTTP",
     "--url", "Podaj URL (np. https://example.com)"),
    ("DirBust", "dirbust.py", "Wielowatkowy fuzzing katalogow",
     "--url", "Podaj URL bazowy (np. http://example.com)"),
    ("HashID", "hashid.py", "Identyfikacja typu hasha",
     "--hash", "Podaj hash do identyfikacji"),
    ("HashCrack", "hashcrack.py", "Slownikowe lamanie hashy MD5/SHA",
     "--hash", "Podaj hash do zlamania"),
    ("XSSProbe", "xssprobe.py", "Tester reflected XSS",
     "--url", "Podaj URL z {PAYLOAD} (np. http://site/?q={PAYLOAD})"),
    ("SQLDetect", "sqldetect.py", "Detektor SQL Injection",
     "--url", "Podaj URL z {PAYLOAD} (np. http://site/?id={PAYLOAD})"),
    ("LogHunter", "loghunter.py", "Analiza logow pod katem atakow",
     "--file", "Podaj sciezke do pliku logu"),
    ("CredLeak", "credleak.py", "Szukacz wyciekow (klucze, tokeny, hasla)",
     "--target", "Podaj sciezke do pliku lub URL"),
]

WARNING_TEXT = (
    "Uzywaj tylko na wlasnych systemach lub z pisemna zgoda wlasciciela.\n"
    "Nieautoryzowane skanowanie i testowanie jest nielegalne."
)


def print_header():
    """Wyswietla baner ASCII i ostrzezenie prawne."""
    console.clear()
    console.print(Text(ascii_banner(), style="bold cyan"))
    console.print(
        "[bold magenta]  Zestaw 10 narzedzi do etycznego testowania bezpieczenstwa[/bold magenta]\n"
    )
    console.print(
        Panel(
            Text(WARNING_TEXT, justify="center", style="bold yellow"),
            title="[bold red]OSTRZEZENIE[/bold red]",
            border_style="yellow",
        )
    )


def print_menu():
    """Wyswietla tabele z lista narzedzi."""
    table = Table(title="Dostepne narzedzia", show_lines=False, title_style="bold cyan")
    table.add_column("#", style="bold yellow", justify="right")
    table.add_column("Narzedzie", style="bold cyan")
    table.add_column("Opis", style="white")

    for i, (name, _script, desc, _flag, _prompt) in enumerate(TOOLS, start=1):
        table.add_row(str(i), name, desc)
    table.add_row("0", "Wyjscie", "Zamknij CyberKit")
    console.print(table)


def run_tool(index):
    """Pobiera dane wejsciowe i uruchamia wybrane narzedzie jako osobny proces."""
    name, script, _desc, flag, prompt_text = TOOLS[index]
    console.print(f"\n[bold cyan]>> {name}[/bold cyan]")
    value = Prompt.ask(f"[yellow]{prompt_text}[/yellow]").strip()
    if not value:
        console.print("[red]Nie podano wartosci - anulowano.[/red]")
        return

    script_path = TOOLS_DIR / script
    cmd = [sys.executable, str(script_path), flag, value]
    console.print(f"[dim]Uruchamiam: {' '.join(cmd)}[/dim]\n")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        console.print("\n[yellow]Przerwano dzialanie narzedzia.[/yellow]")
    except OSError as exc:
        console.print(f"[red]Blad uruchomienia narzedzia:[/red] {exc}")


def main():
    """Glowna petla menu."""
    while True:
        print_header()
        print_menu()
        try:
            choice = Prompt.ask(
                "\n[bold green]Wybierz narzedzie[/bold green]", default="0"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[cyan]Do zobaczenia![/cyan]")
            break

        if choice in ("0", "q", "exit", "quit"):
            console.print("\n[cyan]Do zobaczenia![/cyan]")
            break

        if choice.isdigit() and 1 <= int(choice) <= len(TOOLS):
            run_tool(int(choice) - 1)
            Prompt.ask("\n[dim]Nacisnij Enter, aby wrocic do menu[/dim]", default="")
        else:
            console.print("[red]Nieprawidlowy wybor.[/red]")
            Prompt.ask("\n[dim]Nacisnij Enter, aby kontynuowac[/dim]", default="")


if __name__ == "__main__":
    main()
