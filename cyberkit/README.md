# CyberKit 🛡️

**Zestaw 10 narzędzi do etycznego testowania bezpieczeństwa (ethical hacking) w Pythonie.**

Wszystkie narzędzia uruchamiane są z jednego kolorowego menu (`cyberkit.py`)
lub samodzielnie z linii poleceń. Kod korzysta wyłącznie z biblioteki
standardowej Pythona oraz dwóch zależności: [`rich`](https://github.com/Textualize/rich)
(kolorowy terminal, paski postępu) i [`requests`](https://github.com/psf/requests)
(zapytania HTTP). **Bez zewnętrznych binarek.**

---

## ⚠️ OSTRZEŻENIE

> **Używaj tylko na własnych systemach lub z pisemną zgodą właściciela.**
> Nieautoryzowane skanowanie, testowanie penetracyjne i łamanie zabezpieczeń
> jest nielegalne i może skutkować odpowiedzialnością karną. Autorzy nie
> ponoszą odpowiedzialności za nadużycia. To narzędzie ma charakter
> **edukacyjny i defensywny**.

---

## 📦 Instalacja

```bash
cd cyberkit
python install.py
```

Instalator:
1. Sprawdza i instaluje zależności (`rich`, `requests`).
2. Tworzy katalogi `tools/wordlists/` oraz `reports/`.
3. Generuje domyślne słowniki (jeśli jeszcze nie istnieją).

Ręczna instalacja zależności:

```bash
pip install rich requests
```

---

## 🚀 Uruchomienie

**Menu główne** (interaktywne, ASCII art + lista 1–10):

```bash
python cyberkit.py
```

**Pojedyncze narzędzie** (każde ma własny `argparse`):

```bash
python tools/netspider.py --target 192.168.1.1-254
```

Wszystkie raporty zapisywane są w katalogu `reports/` z nazwą zawierającą
znacznik czasu, np. `reports/netspider_20260810_143512.json`.

---

## 📁 Struktura projektu

```
cyberkit/
├── cyberkit.py            # menu główne (rich, ASCII art)
├── install.py             # instalator zależności + generator słowników
├── README.md
├── tools/
│   ├── common.py          # wspólne funkcje (konsola, zapis raportów, banery)
│   ├── netspider.py       # 1. skaner sieci
│   ├── subsniffer.py      # 2. enumeracja subdomen
│   ├── headerx.py         # 3. analiza nagłówków HTTP
│   ├── dirbust.py         # 4. fuzzing katalogów
│   ├── hashid.py          # 5. identyfikator hashy
│   ├── hashcrack.py       # 6. łamanie haseł słownikowe
│   ├── xssprobe.py        # 7. tester reflected XSS
│   ├── sqldetect.py       # 8. detektor SQL Injection
│   ├── loghunter.py       # 9. analiza logów
│   ├── credleak.py        # 10. szukacz wycieków
│   └── wordlists/
│       ├── subdomains.txt # top 100 subdomen
│       ├── dirs.txt       # 500 ścieżek katalogów
│       └── common.txt     # 100 popularnych haseł
└── reports/               # tu trafiają raporty (JSON / Markdown)
```

---

## 🧰 Narzędzia

### 1. NetSpider — skaner sieci
Ping sweep (systemowy `ping` przez `subprocess`) + TCP connect scan top 100
portów (`socket`). Rozpoznaje aktywne hosty i otwarte porty wraz z nazwami usług.

```bash
python tools/netspider.py --target 192.168.1.1-254
python tools/netspider.py --target scanme.nmap.org --ports 22,80,443
python tools/netspider.py --target 10.0.0.5 --skip-ping
```
**Wyjście:** tabela hostów + otwarte porty → `reports/netspider_*.json`

---

### 2. SubSniffer — enumeracja subdomen
Wczytuje słownik subdomen i sprawdza rekordy DNS przez `socket.gethostbyname`.

```bash
python tools/subsniffer.py --domain example.com
python tools/subsniffer.py --domain example.com --wordlist moj_slownik.txt
```
**Wyjście:** znalezione subdomeny z IP → `reports/subsniffer_*.json`

---

### 3. HeaderX — analiza nagłówków HTTP
Pobiera nagłówki odpowiedzi (`requests`), sprawdza obecność nagłówków
bezpieczeństwa (HSTS, CSP, X-Frame-Options, X-XSS-Protection,
X-Content-Type-Options, Referrer-Policy, Permissions-Policy) i ocenia ryzyko:
**LOW / MEDIUM / HIGH / CRITICAL**.

```bash
python tools/headerx.py --url https://example.com
python tools/headerx.py --url http://localhost:8080 --insecure
```
**Wyjście:** raport Markdown → `reports/headerx_*.md`

---

### 4. DirBust — fuzzing katalogów
Wielowątkowo (domyślnie 10 wątków) wysyła zapytania GET na ścieżki ze słownika
(500 pozycji) i raportuje interesujące kody statusu (200, 301, 302, 403, 500...).

```bash
python tools/dirbust.py --url http://example.com
python tools/dirbust.py --url http://example.com --threads 20
```
**Wyjście:** znalezione ścieżki + statusy → `reports/dirbust_*.json`

---

### 5. HashID — identyfikator hashy
Na podstawie długości i wyrażeń regularnych rozpoznaje typ hasha:
MD5, SHA1, SHA256, SHA512, bcrypt, NTLM (oraz pokrewne).

```bash
python tools/hashid.py --hash 5f4dcc3b5aa765d61d8327deb882cf99
```
**Wyjście:** lista możliwych typów → `reports/hashid_*.json`

---

### 6. HashCrack — słownikowe łamanie haseł
Wczytuje hash i słownik, porównuje MD5/SHA1/SHA256/SHA512 (`hashlib`).
Algorytm wykrywany automatycznie z długości hasha.

```bash
python tools/hashcrack.py --hash 5f4dcc3b5aa765d61d8327deb882cf99
python tools/hashcrack.py --hash <sha1> --algo sha1 --wordlist rockyou.txt
```
**Wyjście:** znalezione hasło lub „not found” → `reports/hashcrack_*.json`

---

### 7. XSSProbe — tester reflected XSS
Wysyła zestaw payloadów XSS w miejsce `{PAYLOAD}` i sprawdza, czy zostały
odbite (reflected) w odpowiedzi bez zakodowania.

```bash
python tools/xssprobe.py --url "http://site/search?q={PAYLOAD}"
```
**Wyjście:** lista działających payloadów → `reports/xssprobe_*.json`

---

### 8. SQLDetect — detektor SQL Injection
Wysyła klasyczne payloady SQLi w miejsce `{PAYLOAD}` i analizuje odpowiedź:
komunikaty błędów SQL, zmiana długości, zmiana statusu (względem baseline).

```bash
python tools/sqldetect.py --url "http://site/item?id={PAYLOAD}"
```
**Wyjście:** potencjalne podatności → `reports/sqldetect_*.json`

---

### 9. LogHunter — analiza logów
Parsuje log (Apache/Nginx combined lub generyczny) i szuka wzorców ataków:
SQLi, XSS, LFI/Path Traversal, RCE/Shellshock oraz brute force.

```bash
python tools/loghunter.py --file /var/log/apache2/access.log
python tools/loghunter.py --file access.log --bruteforce-threshold 30
```
**Wyjście:** statystyki + alerty z numerami linii → `reports/loghunter_*.json`

---

### 10. CredLeak — szukacz wycieków
Skanuje plik lub stronę pod kątem wzorców wrażliwych danych: klucze API
(Google `AIza...`, Stripe `sk_live/pk_live`, AWS `AKIA...`, GitHub, Slack),
tokeny JWT, klucze prywatne, hasła w konfiguracji, adresy e-mail i IP.
Wartości sekretów są maskowane.

```bash
python tools/credleak.py --target config.js
python tools/credleak.py --target https://example.com/app.js
```
**Wyjście:** znaleziska pogrupowane wg kategorii → `reports/credleak_*.json`

---

## 🔧 Wymagania

- Python 3.7+
- `rich`
- `requests`
- systemowe polecenie `ping` (dla NetSpider)

---

## 📄 Licencja i odpowiedzialność

Projekt edukacyjny. Korzystając z CyberKit, akceptujesz, że ponosisz pełną
odpowiedzialność za sposób jego użycia. **Testuj wyłącznie systemy, do których
masz prawo.**
