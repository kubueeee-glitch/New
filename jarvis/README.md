# Jarvis — desktopowy asystent AI

Asystent w stylu „Jarvisa" jako aplikacja desktopowa (Electron). Mózgiem może
być **Claude (API Anthropic)** albo **model lokalny przez Ollamę (za darmo,
offline)** — wybierasz w ustawieniach. Wokół niego zbudowano **zespół agentów
działających równolegle**, głos z wake wordem, research z rosnącą bazą wiedzy,
pełne sterowanie komputerem i warstwę skanowania bezpieczeństwa — wszystko w
futurystycznym interfejsie HUD.

> Interfejs, komunikaty i osobowość są po polsku.

---

## Co potrafi

- **🧠 Wielu agentów naraz** — orkiestrator *Jarvis* rozkłada polecenie na
  podzadania i deleguje je do wyspecjalizowanych agentów, którzy pracują
  **równolegle**:
  - **Researcher** — szuka w internecie i buduje bazę wiedzy,
  - **Operator** — steruje komputerem (aplikacje, klikanie, pisanie, pliki, system),
  - **Guard** — skanuje pliki i procesy pod kątem bezpieczeństwa,
  - **Archivist** — notatki, pamięć, pliki, makra.
  W panelu „Rój agentów" widać na żywo, kto co robi.
- **🎙️ Głos + wake word „Hej Jarvis"** — mówisz, Jarvis rozumie i odpowiada
  głosem. Nasłuch ciągły z wykrywaniem słowa-klucza lub na przycisk.
- **🔎 Research i „uczenie się"** — Jarvis wyszukuje w sieci (narzędzie
  `web_search`), zapisuje ustrukturyzowane notatki ze źródłami do bazy wiedzy,
  a przy kolejnych pytaniach z niej korzysta. Ponowny research **pogłębia**
  istniejący temat — im częściej pytasz, tym lepiej „ogarnia".
- **🖱️ Pełne sterowanie komputerem** — otwiera aplikacje i strony, klika i
  pisze (nut-js), steruje głośnością i multimediami, zarządza plikami i oknami,
  a gdy trzeba — „patrzy" na ekran (zrzut + analiza wizualna) i działa po
  współrzędnych. Może wykonywać polecenia PowerShell/shell.
- **🛡️ Warstwa bezpieczeństwa** — liczy SHA-256 plików i sprawdza je w
  VirusTotal, pilnuje folderu Pobrane, podgląda procesy i przenosi podejrzane
  pliki do kwarantanny.
- **🧠 Pamięć długoterminowa** — zapamiętuje fakty o Tobie między rozmowami.
- **✨ HUD w stylu Iron Mana** — animowany „reaktor" ze stanami, rój agentów,
  wizualizacja głosu, panele Wiedzy / Bezpieczeństwa / Logu / Ustawień, tray,
  globalne skróty.

---

## Wymagania

- **Node.js 18+** (zalecane 20+)
- **Mózg AI — jedno z dwóch:**
  - **Ollama** (za darmo, lokalnie) — [ollama.com](https://ollama.com), patrz sekcja niżej, **albo**
  - **Klucz API Anthropic** — z [console.anthropic.com](https://console.anthropic.com) (płatne za użycie).
- **Klucz VirusTotal** (opcjonalny, darmowy) — do skanowania plików.
- Do sterowania myszą/klawiaturą: biblioteka `nut-js` instaluje się z `npm install`
  (na niektórych systemach może wymagać narzędzi kompilacji).

> Research (wyszukiwanie w internecie) działa za darmo przez DuckDuckGo — bez
> żadnego klucza — niezależnie od wybranego mózgu AI.

## Za darmo — tryb Ollama (lokalnie, offline)

Model działa na Twoim komputerze: 0 zł, prywatnie, bez internetu (poza researchem).

1. Zainstaluj **Ollama** z [ollama.com](https://ollama.com).
2. Pobierz model z dobrą obsługą narzędzi (w terminalu):
   ```bash
   ollama pull qwen2.5:7b        # lekki, szybki (~5 GB, mieści się na 8 GB VRAM)
   # ollama pull qwen2.5:14b     # mocniejszy, jeśli masz zapas VRAM/RAM
   ```
3. Upewnij się, że Ollama działa (zwykle startuje sama; ewentualnie `ollama serve`).
4. W Jarvisie: **⚙ Ustawienia → Silnik AI → „Ollama"**, wpisz model (np. `qwen2.5:7b`) i zapisz.

Zalecany sprzęt: karta z ~8 GB VRAM (np. RTX 3060 Ti) i 16 GB+ RAM dla modeli 7–8B.
Model lokalny 7–8B jest słabszy od Claude w złożonej orkiestracji wielu agentów,
ale do większości zadań w zupełności wystarcza.

## Uruchomienie

```bash
cd jarvis
npm install
npm start
```

Przy pierwszym starcie otwórz **⚙ Ustawienia** i albo przełącz **Silnik AI** na
**Ollamę** (za darmo), albo wklej klucz API Anthropic.

## Zbudowanie instalatora (opcjonalnie)

```bash
npm run build        # bieżący system
npm run build:win    # .exe (NSIS) na Windows
```

Wynik trafia do `dist/`. Aplikacja nie jest podpisana cyfrowo — patrz uwaga
o SmartScreen w ograniczeniach.

## Skróty

- `Ctrl/Cmd + Shift + J` — pokaż/ukryj Jarvisa
- `Ctrl/Cmd + Shift + X` — **STOP** automatyzacji

---

## Architektura

```
jarvis/
  main.js            proces główny: okno HUD, tray, IPC, skróty, trwałość danych
  preload.js         bezpieczny mostek IPC (contextBridge)
  agents/
    anthropic.js     klient Claude API (Node fetch, bez CORS)
    runner.js        pętla tool_use jednego agenta (+ wizja, przerwanie, limity)
    registry.js      definicje wyspecjalizowanych agentów
    orchestrator.js  Jarvis: dekompozycja i równoległe uruchamianie agentów
    llm.js           wybór providera (Anthropic / Ollama)
    providers/       anthropic.js, ollama.js — znormalizowany format wiadomości
  tools/
    system.js        aplikacje, URL, system, schowek, polecenia, pliki
    automation.js    mysz/klawiatura/okna (nut-js) + zrzut ekranu (wizja)
    security.js      skaner VirusTotal, watcher Pobranych, procesy, kwarantanna
    knowledge.js     pamięć, notatki, baza wiedzy, data, kalkulator, makra
    websearch.js     darmowe wyszukiwanie w sieci (DuckDuckGo, bez klucza)
  renderer/          interfejs HUD (index.html, style.css, app.js) + głos
```

Agenci i narzędzia żyją w procesie głównym (Node — brak problemów z CORS, klucz
API nie trafia do warstwy web). Renderer odpowiada za interfejs oraz głos
(synteza mowy i rozpoznawanie mowy). Warstwa `llm` tłumaczy neutralny format
wiadomości na wybrany silnik (Claude API albo lokalna Ollama), więc ten sam
kod agentów działa z oboma.

---

## Ograniczenia (przeczytaj)

1. **„Antywirus" to skaner VirusTotal, nie pełny antywirus** — nie ma własnego
   silnika sygnatur ani ochrony w czasie rzeczywistym na poziomie jądra. **Nie
   zastępuje Windows Defendera** — współpracuje z nim.
2. **Model się nie dotrenowuje.** „Uczenie się" to rosnąca baza notatek z
   researchu, a nie zmiana wag modelu. Świeże informacje wymagają researchu.
3. **Koszt zależy od wybranego mózgu.** Tryb Anthropic jest płatny za użycie
   (API to nie to samo co subskrypcja Claude.ai — trzeba doładować konto).
   Tryb **Ollama jest darmowy** (model lokalny). Research przez DuckDuckGo jest
   darmowy w obu trybach, ale wymaga internetu. Skanowanie wymaga (darmowego)
   klucza VirusTotal. Synteza mowy działa lokalnie.
4. **Rozpoznawanie mowy zależy od środowiska.** Wykorzystuje Web Speech API
   przeglądarki Chromium — w niektórych buildach Electrona bywa zawodne lub
   niedostępne (błąd `network`); wtedy działa pole tekstowe. Wake word wymaga
   stale włączonego mikrofonu, zużywa zasoby i bywa zawodny (hałas, fałszywe
   wyzwolenia).
5. **Automatyzacja GUI bywa krucha.** Klikanie po współrzędnych/wizji może
   chybić przy zmianie układu ekranu, rozdzielczości czy języka aplikacji —
   dlatego jest hotkey STOP i limit kroków.
6. **Działa, dopóki aplikacja jest uruchomiona** (może być w zasobniku). Po
   zamknięciu nasłuch, watcher i przypomnienia nie działają. Autostart jest
   opcjonalny.
7. **Pełne sterowanie = pełna odpowiedzialność.** Pomyłka modelu może wykonać
   złą akcję, dlatego **wszystko nieodwracalne** (usuwanie plików, wyłączenie
   komputera, polecenia powłoki) **wymaga Twojego potwierdzenia**, a akcje
   trafiają do widocznego logu.
8. **SmartScreen / antywirus może ostrzegać.** Program steruje systemem i
   wykonuje polecenia, a instalator nie jest podpisany cyfrowo — to normalne dla
   narzędzi automatyzacji, trzeba potwierdzić uruchomienie.
9. **Dane są lokalne, na jednym urządzeniu.** Wiedza, pamięć i klucze nie
   synchronizują się między komputerami.

### Świadomie poza zakresem (granica bezpieczeństwa)

Ten asystent jest przeznaczony do użytku na **własnym komputerze**. Celowo **nie**
zawiera i nie będzie zawierał: ukrytego/niewidocznego działania i szpiegowania,
keyloggera, przechwytywania haseł, wyłączania lub manipulowania zabezpieczeniami
(np. Windows Defender), samo-rozprzestrzeniania ani narzędzi do atakowania innych
maszyn. To są funkcje, które mają sens wyłącznie do wyrządzania szkody.

---

## Licencja

MIT.
