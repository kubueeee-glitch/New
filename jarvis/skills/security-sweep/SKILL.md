---
name: Kontrola bezpieczeństwa
description: Gdy użytkownik prosi o sprawdzenie bezpieczeństwa komputera — przeskanuj procesy i podejrzane pliki, podaj werdykt.
---

# Kontrola bezpieczeństwa

Deleguj do agenta **Guard**.

## Procedura
1. `list_processes` — przejrzyj listę, wskaż nietypowe (nieznane nazwy, procesy z folderów tymczasowych).
2. Jeśli użytkownik wskazał plik lub jest świeży plik w Pobranych — `scan_file` (VirusTotal).
3. Zbierz werdykt:
   - **Czysto** — brak wykryć.
   - **Podejrzane/Złośliwe** — ile silników flaguje + rekomendacja kwarantanny (`quarantine_file` za zgodą).
4. Bądź uczciwy: to skaner (VirusTotal), nie pełny antywirus — nie zastępuje Windows Defendera.

## Zasady
- Nie zabijaj procesów i nie usuwaj plików bez wyraźnej zgody użytkownika.
