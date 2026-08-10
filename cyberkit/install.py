#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install.py - Instalator zestawu CyberKit.

Zadania:
  1. Sprawdza i (w razie potrzeby) instaluje zależności: rich, requests.
  2. Tworzy strukturę katalogów: tools/wordlists/ oraz reports/.
  3. Generuje domyślne słowniki, jeśli jeszcze nie istnieją:
       - tools/wordlists/subdomains.txt  (top 100 subdomen)
       - tools/wordlists/dirs.txt        (500 ścieżek katalogów/plików)
       - tools/wordlists/common.txt      (100 popularnych haseł)

Uruchomienie:
    python install.py
"""

import importlib
import subprocess
import sys
from pathlib import Path

# Korzeń pakietu to katalog, w którym leży ten plik.
PKG_ROOT = Path(__file__).resolve().parent
TOOLS_DIR = PKG_ROOT / "tools"
WORDLISTS_DIR = TOOLS_DIR / "wordlists"
REPORTS_DIR = PKG_ROOT / "reports"

# Lista wymaganych pakietów: (nazwa_do_importu, nazwa_do_pip).
REQUIRED = [
    ("rich", "rich"),
    ("requests", "requests"),
]


# ---------------------------------------------------------------------------
# 1. Zależności
# ---------------------------------------------------------------------------
def check_and_install():
    """Sprawdza dostępność zależności i instaluje brakujące przez pip."""
    for import_name, pip_name in REQUIRED:
        try:
            importlib.import_module(import_name)
            print(f"[OK]  Pakiet '{import_name}' jest juz zainstalowany.")
        except ImportError:
            print(f"[..]  Instaluje brakujacy pakiet '{pip_name}'...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pip_name]
                )
                print(f"[OK]  Zainstalowano '{pip_name}'.")
            except subprocess.CalledProcessError:
                print(
                    f"[!!]  Nie udalo sie zainstalowac '{pip_name}'. "
                    f"Sprobuj recznie: pip install {pip_name}"
                )


# ---------------------------------------------------------------------------
# 2. Katalogi
# ---------------------------------------------------------------------------
def create_dirs():
    """Tworzy wymagane katalogi, jeśli nie istnieją."""
    for d in (TOOLS_DIR, WORDLISTS_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
        print(f"[OK]  Katalog gotowy: {d}")


# ---------------------------------------------------------------------------
# 3. Dane słowników
# ---------------------------------------------------------------------------
def subdomains_wordlist():
    """Zwraca listę 100 najpopularniejszych subdomen."""
    subs = [
        "www", "mail", "ftp", "webmail", "smtp", "pop", "pop3", "imap", "ns1",
        "ns2", "ns3", "ns4", "dns", "dns1", "dns2", "mx", "mx1", "mx2", "email",
        "webdisk", "admin", "cpanel", "whm", "autodiscover", "autoconfig", "m",
        "mobile", "test", "dev", "staging", "beta", "demo", "blog", "forum",
        "forums", "news", "vpn", "remote", "portal", "intranet", "extranet",
        "secure", "shop", "store", "api", "cdn", "static", "media", "images",
        "img", "assets", "files", "download", "downloads", "upload", "uploads",
        "docs", "wiki", "help", "support", "kb", "status", "monitor", "stats",
        "analytics", "search", "db", "database", "mysql", "sql", "phpmyadmin",
        "pma", "server", "host", "proxy", "gateway", "router", "firewall",
        "backup", "old", "new", "app", "apps", "web", "web1", "web2", "www2",
        "www3", "git", "svn", "jenkins", "ci", "jira", "confluence", "chat",
        "video", "voip", "sip", "crm", "erp", "cms", "office", "exchange",
        "owa", "lync",
    ]
    return subs[:100]


def passwords_wordlist():
    """Zwraca listę 100 najpopularniejszych haseł (do testów słownikowych)."""
    return [
        "123456", "password", "12345678", "qwerty", "123456789", "12345",
        "1234", "111111", "1234567", "dragon", "123123", "baseball", "abc123",
        "football", "monkey", "letmein", "shadow", "master", "666666",
        "qwertyuiop", "123321", "mustang", "1234567890", "michael", "654321",
        "superman", "1qaz2wsx", "7777777", "121212", "000000", "qazwsx",
        "123qwe", "killer", "trustno1", "jordan", "jennifer", "zxcvbnm",
        "asdfgh", "hunter", "buster", "soccer", "harley", "batman", "andrew",
        "tigger", "sunshine", "iloveyou", "2000", "charlie", "robert", "thomas",
        "hockey", "ranger", "daniel", "starwars", "klaster", "112233",
        "george", "computer", "michelle", "jessica", "pepper", "1111", "zxcvbn",
        "555555", "11111111", "131313", "freedom", "777777", "pass", "maggie",
        "159753", "aaaaaa", "ginger", "princess", "joshua", "cheese", "amanda",
        "summer", "love", "ashley", "nicole", "chelsea", "biteme", "matthew",
        "access", "yankees", "987654321", "dallas", "austin", "thunder",
        "taylor", "matrix", "william", "corvette", "hello", "martin", "heather",
        "secret", "merlin",
    ]


def dirs_wordlist():
    """
    Buduje listę 500 ścieżek katalogów/plików używanych w fuzzingu.
    Powstaje z kilku kategorii, deduplikowana i przycinana do dokładnie 500.
    """
    core = [
        # Panele administracyjne / uwierzytelnianie
        "admin", "administrator", "admin.php", "admin/login", "admin/index.php",
        "adminpanel", "admin_area", "adminarea", "administration", "controlpanel",
        "cpanel", "webadmin", "sysadmin", "moderator", "login", "login.php",
        "logout", "signin", "sign-in", "signup", "register", "auth", "oauth",
        "sso", "account", "accounts", "profile", "user", "users", "member",
        "members", "dashboard", "panel", "manage", "manager", "management",
        "console", "wp-admin", "wp-login.php", "wp-content", "wp-includes",
        "wp-config.php", "wp-json", "xmlrpc.php",
        # Konfiguracja / sekrety
        "config", "config.php", "configuration", "settings", "settings.php",
        "setup", "install", "install.php", "installer", ".env", ".env.local",
        ".env.backup", "env", ".git", ".git/config", ".git/HEAD", ".gitignore",
        ".svn", ".hg", ".htaccess", ".htpasswd", ".bash_history", ".ssh",
        "id_rsa", "credentials", "secret", "secrets", "private", "keys",
        "apikeys", "token", "tokens",
        # Kopie zapasowe / dumpy
        "backup", "backups", "bak", "old", "new", "temp", "tmp", "cache",
        "dump", "dumps", "export", "exports", "archive", "archives",
        # Pliki serwera / status
        "server-status", "server-info", "status", "health", "healthcheck",
        "ping", "info.php", "phpinfo.php", "test.php", "test", "debug",
        "trace.axd", "elmah.axd", "web.config", "robots.txt", "sitemap.xml",
        "sitemap", "crossdomain.xml", "clientaccesspolicy.xml", "humans.txt",
        "security.txt", ".well-known", ".well-known/security.txt",
        # Bazy danych / narzędzia
        "phpmyadmin", "pma", "mysql", "myadmin", "dbadmin", "adminer",
        "adminer.php", "database", "db", "sql", "backup.sql", "dump.sql",
        # Katalogi statyczne
        "images", "img", "image", "css", "js", "javascript", "scripts",
        "static", "assets", "media", "fonts", "styles", "public", "resources",
        "content", "files", "file", "documents", "docs", "doc", "download",
        "downloads", "upload", "uploads", "data", "storage", "store",
        # Aplikacja / API
        "api", "api/v1", "api/v2", "api/v3", "rest", "graphql", "soap", "rpc",
        "webservice", "webservices", "service", "services", "app", "application",
        "includes", "include", "inc", "lib", "libs", "library", "vendor",
        "src", "core", "modules", "module", "plugins", "plugin", "components",
        "component", "templates", "template", "themes", "theme", "views",
        "controllers", "models", "helpers", "classes", "functions",
        # CMS-y
        "administrator/index.php", "joomla", "drupal", "typo3", "magento",
        "prestashop", "opencart", "sites/default", "user/login", "admin/config",
        # Logi / raporty
        "log", "logs", "error_log", "access_log", "error.log", "access.log",
        "debug.log", "logfile", "report", "reports",
        # Poczta / komunikacja
        "webmail", "mail", "email", "roundcube", "squirrelmail", "owa",
        # Testowe / dev
        "dev", "development", "staging", "stage", "beta", "demo", "sandbox",
        "qa", "uat", "local", "example", "sample", "samples", "tmp2",
        # Płatności / e-commerce
        "cart", "checkout", "payment", "payments", "order", "orders", "invoice",
        "invoices", "shop", "shopping", "products", "product", "catalog",
        # Inne popularne
        "search", "feed", "rss", "atom", "news", "blog", "forum", "board",
        "wiki", "help", "faq", "about", "contact", "home", "index", "index.php",
        "index.html", "default", "default.php", "main", "portal", "intranet",
        "extranet", "vpn", "remote", "proxy", "gateway", "cgi-bin", "bin",
        "scripts2", "system", "sys", "internal", "hidden", "private2",
    ]

    # Kombinacje: typowe nazwy plików kopii zapasowych.
    backup_names = ["backup", "www", "site", "web", "db", "database", "dump",
                    "data", "sql", "old", "wwwroot", "public_html"]
    backup_exts = [".zip", ".tar.gz", ".tar", ".gz", ".sql", ".bak", ".rar",
                   ".7z", ".tgz", ".old"]
    combos = [f"{n}{e}" for n in backup_names for e in backup_exts]

    # Kombinacje: numerowane wersje kopii / katalogów.
    numbered = []
    for base in ["backup", "old", "test", "temp", "site", "www", "v", "release"]:
        for i in range(1, 11):
            numbered.append(f"{base}{i}")

    # Łączymy wszystko, usuwamy duplikaty zachowując kolejność.
    seen = set()
    result = []
    for item in core + combos + numbered:
        if item not in seen:
            seen.add(item)
            result.append(item)

    # Dokładnie 500 wpisów: jeśli za mało, dopełniamy sensownymi wzorcami.
    filler_bases = ["dir", "folder", "path", "page", "node", "item", "res"]
    i = 0
    while len(result) < 500:
        base = filler_bases[i % len(filler_bases)]
        candidate = f"{base}{i}"
        if candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
        i += 1

    return result[:500]


# ---------------------------------------------------------------------------
# 4. Zapis słowników
# ---------------------------------------------------------------------------
def write_wordlist(path, lines):
    """Zapisuje listę słów do pliku (po jednym w wierszu), jeśli plik nie istnieje."""
    if path.exists():
        print(f"[--]  Slownik juz istnieje, pomijam: {path.name}")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[OK]  Utworzono slownik: {path.name} ({len(lines)} wpisow)")


def create_wordlists():
    """Tworzy wszystkie domyślne słowniki (bez nadpisywania istniejących)."""
    write_wordlist(WORDLISTS_DIR / "subdomains.txt", subdomains_wordlist())
    write_wordlist(WORDLISTS_DIR / "dirs.txt", dirs_wordlist())
    write_wordlist(WORDLISTS_DIR / "common.txt", passwords_wordlist())


# ---------------------------------------------------------------------------
# Główny punkt wejścia
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print(" CyberKit - instalator")
    print("=" * 60)
    print("\n[1/3] Sprawdzanie zaleznosci...")
    check_and_install()
    print("\n[2/3] Tworzenie katalogow...")
    create_dirs()
    print("\n[3/3] Generowanie slownikow...")
    create_wordlists()
    print("\nGotowe! Uruchom menu:  python cyberkit.py")


if __name__ == "__main__":
    main()
