#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netspider.py - Skaner sieci CyberKit.

Funkcje:
  * Ping sweep - wykrywa aktywne hosty za pomocą systemowego polecenia ping.
  * TCP connect scan - sprawdza top 100 portów TCP przy użyciu gniazd (socket).

Wejście:
  --target  pojedynczy adres IP (192.168.1.10) lub zakres (192.168.1.1-254),
            albo nazwa hosta.

Wyjście:
  Kolorowa tabela hostów z otwartymi portami oraz raport JSON
  w katalogu reports/ (netspider_TIMESTAMP.json).

Przykłady:
    python tools/netspider.py --target 192.168.1.1-254
    python tools/netspider.py --target scanme.nmap.org --ports 22,80,443
"""

import argparse
import platform
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import console, print_banner, save_json
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# Top 100 portów TCP (kolejność wg popularności, na podstawie nmap top-100).
TOP_100_PORTS = [
    7, 9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 88, 106, 110, 111, 113,
    119, 135, 139, 143, 144, 179, 199, 389, 427, 443, 444, 445, 465, 513, 514,
    515, 543, 544, 548, 554, 587, 631, 646, 873, 990, 993, 995, 1025, 1026,
    1027, 1028, 1029, 1110, 1433, 1720, 1723, 1755, 1900, 2000, 2001, 2049,
    2121, 2717, 3000, 3128, 3306, 3389, 3986, 4899, 5000, 5009, 5051, 5060,
    5101, 5190, 5357, 5432, 5631, 5666, 5800, 5900, 6000, 6001, 6646, 7070,
    8000, 8008, 8009, 8080, 8081, 8443, 8888, 9100, 9999, 10000, 32768, 49152,
    49153, 49154, 49155, 49156, 49157,
]

# Mapowanie najpopularniejszych portów na nazwy usług (do czytelnego raportu).
SERVICES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http",
    110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios", 143: "imap",
    443: "https", 445: "smb", 465: "smtps", 587: "submission", 993: "imaps",
    995: "pop3s", 1433: "mssql", 1723: "pptp", 3306: "mysql", 3389: "rdp",
    5432: "postgresql", 5900: "vnc", 6379: "redis", 8080: "http-proxy",
    8443: "https-alt", 27017: "mongodb",
}


def parse_target(target):
    """
    Zamienia zapis celu na listę adresów IP/hostów.

    Obsługiwane formaty:
      * "192.168.1.10"      -> pojedynczy host
      * "192.168.1.1-254"   -> zakres ostatniego oktetu
      * "example.com"       -> nazwa hosta (bez rozwijania)
    """
    target = target.strip()
    if "-" in target and target.count(".") == 3:
        # Zakres w ostatnim oktecie, np. 192.168.1.1-254
        prefix, last = target.rsplit(".", 1)
        if "-" in last:
            start_s, end_s = last.split("-", 1)
            try:
                start, end = int(start_s), int(end_s)
            except ValueError:
                return [target]
            if 0 <= start <= end <= 255:
                return [f"{prefix}.{i}" for i in range(start, end + 1)]
    return [target]


def ping_host(ip, timeout=1):
    """
    Sprawdza, czy host odpowiada na ping (subprocess).
    Zwraca True, gdy host jest aktywny.
    """
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def scan_port(ip, port, timeout=0.5):
    """
    Próba nawiązania połączenia TCP z portem (socket.connect_ex).
    Zwraca numer portu, jeśli jest otwarty, w przeciwnym razie None.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            if sock.connect_ex((ip, port)) == 0:
                return port
    except OSError:
        pass
    return None


def scan_host_ports(ip, ports, timeout=0.5, workers=100):
    """Skanuje wszystkie porty danego hosta równolegle. Zwraca posortowaną listę."""
    open_ports = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(scan_port, ip, p, timeout) for p in ports]
        for fut in as_completed(futures):
            port = fut.result()
            if port is not None:
                open_ports.append(port)
    return sorted(open_ports)


def run(target, ports, ping_timeout=1, port_timeout=0.5, skip_ping=False):
    """Główna logika skanera: ping sweep + skan portów aktywnych hostów."""
    hosts = parse_target(target)
    console.print(f"[cyan]Cel:[/cyan] {target}  ([bold]{len(hosts)}[/bold] adresow)")

    # --- Etap 1: ping sweep ---
    alive = []
    if skip_ping:
        # Pomijamy ping - traktujemy wszystkie adresy jako potencjalnie aktywne.
        alive = hosts
        console.print("[yellow]Pomijam ping sweep (--skip-ping).[/yellow]")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Ping sweep...", total=len(hosts))
            with ThreadPoolExecutor(max_workers=50) as pool:
                futures = {pool.submit(ping_host, ip, ping_timeout): ip for ip in hosts}
                for fut in as_completed(futures):
                    ip = futures[fut]
                    if fut.result():
                        alive.append(ip)
                    progress.advance(task)
        alive.sort(key=lambda x: [int(o) if o.isdigit() else o for o in x.split(".")])
        console.print(f"[green]Aktywne hosty:[/green] {len(alive)}")

    # --- Etap 2: skan portów ---
    results = []
    if alive:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Skan portow...", total=len(alive))
            for ip in alive:
                open_ports = scan_host_ports(ip, ports, port_timeout)
                results.append({
                    "ip": ip,
                    "alive": True,
                    "open_ports": [
                        {"port": p, "service": SERVICES.get(p, "unknown")}
                        for p in open_ports
                    ],
                })
                progress.advance(task)

    render_table(results)

    report = {
        "tool": "netspider",
        "target": target,
        "hosts_scanned": len(hosts),
        "hosts_alive": len(alive),
        "ports_checked": len(ports),
        "results": results,
    }
    save_json("netspider", report)
    return report


def render_table(results):
    """Wyświetla wyniki w kolorowej tabeli rich."""
    table = Table(title="NetSpider - wyniki skanowania", show_lines=True)
    table.add_column("Host", style="bold cyan")
    table.add_column("Status", style="green")
    table.add_column("Otwarte porty", style="yellow")

    if not results:
        console.print("[yellow]Brak aktywnych hostow.[/yellow]")
        return

    for host in results:
        ports = host["open_ports"]
        if ports:
            ports_str = ", ".join(
                f"{p['port']}/{p['service']}" for p in ports
            )
        else:
            ports_str = "[dim]brak[/dim]"
        table.add_row(host["ip"], "aktywny", ports_str)
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="NetSpider - skaner sieci (ping sweep + TCP connect scan)."
    )
    parser.add_argument(
        "--target", "-t", required=True,
        help="Adres IP, zakres (192.168.1.1-254) lub nazwa hosta.",
    )
    parser.add_argument(
        "--ports", "-p", default=None,
        help="Lista portow oddzielona przecinkami (domyslnie top 100).",
    )
    parser.add_argument(
        "--skip-ping", action="store_true",
        help="Pomija ping sweep i od razu skanuje porty.",
    )
    parser.add_argument(
        "--timeout", type=float, default=0.5,
        help="Timeout polaczenia TCP w sekundach (domyslnie 0.5).",
    )
    args = parser.parse_args()

    print_banner("NETSPIDER", "Skaner sieci: ping sweep + TCP connect scan (top 100 portow)")

    if args.ports:
        try:
            ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
        except ValueError:
            console.print("[red]Bledna lista portow.[/red]")
            return
    else:
        ports = TOP_100_PORTS

    run(args.target, ports, port_timeout=args.timeout, skip_ping=args.skip_ping)


if __name__ == "__main__":
    main()
