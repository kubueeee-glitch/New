# AI Shop — asystent zakupowy + sterowanie telefonem (Android)

Natywna apka Android. Wpisujesz albo mówisz po polsku co chcesz, Gemini 2.0 Flash
rozumie intencję, a apka:
- otwiera wyszukiwarki polskich sklepów (Allegro, OLX, Ceneo, x-kom, Media Expert, Morele, Empik, Zalando, Google Shopping) z gotowym zapytaniem,
- ściąga i porównuje ceny z Ceneo i Google Shopping w jednym widoku,
- otwiera dowolną apkę na telefonie ("otwórz YouTube", "włącz Spotify"),
- przez Accessibility Service klika, wpisuje i scrolluje w innych apkach
  ("wyślij wiadomość do Maćka na WhatsApp: jestem za 10 minut").

## Wymagania
- Android Studio (Hedgehog albo nowszy)
- JDK 17 (wbudowany w Android Studio)
- Telefon Android 8.0+ albo emulator z Google Play
- Darmowy klucz Gemini z https://aistudio.google.com (ikona "Get API key")

## Uruchomienie
1. Otwórz katalog `android/` w Android Studio (File → Open).
2. Poczekaj aż Gradle zsynchronizuje zależności.
3. Podłącz telefon (z włączonym debugowaniem USB) lub odpal emulator.
4. Run ▶ — apka się zainstaluje.

## Pierwsze użycie
1. Po starcie kliknij ikonę zębatki (Ustawienia) → wpisz klucz Gemini → Zapisz.
2. Aby AI mogło klikać w innych apkach: w Ustawieniach apki kliknij
   "Otwórz Ustawienia Dostępności" → włącz "AI Shop". (Krok opcjonalny —
   wyszukiwanie w sklepach i otwieranie apek działa bez tego.)
3. Mów (przycisk mikrofonu) albo pisz, np.:
   - „znajdź czarne buty Nike rozmiar 42 do 300 zł”
   - „pokaż gry na PS5 do 200 zł na Allegro i Ceneo”
   - „otwórz YouTube"
   - „wyszukaj na YouTube koncert Daft Punk” (wymaga włączonej Dostępności)

## Architektura
- `MainActivity.kt` — UI w Jetpack Compose (czat + mikrofon + ustawienia).
- `ai/GeminiClient.kt` — REST do `gemini-2.0-flash`, zwraca strukturyzowany JSON.
- `ai/Action.kt` — schemat intencji: SEARCH_SHOPS, OPEN_APP, PHONE_CONTROL, WEB_SEARCH, ANSWER.
- `voice/VoiceRecognizer.kt` — wbudowany Android `SpeechRecognizer`, język pl-PL.
- `shops/ShopRegistry.kt` — generuje URL-e wyszukiwania dla 9 sklepów.
- `shops/PriceComparator.kt` — Jsoup scrapuje Ceneo + Google Shopping.
- `control/PhoneControlService.kt` — `AccessibilityService` z klikaniem/typing/scroll.
- `control/ActionExecutor.kt` — uruchamia apki po pakiecie i wykonuje sekwencje kroków.
- `prefs/AppPrefs.kt` — `EncryptedSharedPreferences` na klucz API.

## Limity i uwagi
- Darmowy tier Gemini: ~15 req/min, 1500/dzień — w zupełności wystarczy.
- Scraping Ceneo/Google: selektory mogą się zmieniać. Gdy nic nie znajdzie,
  apka i tak otworzy linki bezpośrednio do sklepów.
- AccessibilityService jest mocny — używaj rozważnie. Apka klika TYLKO to,
  co Gemini umieści w `steps[]` w odpowiedzi na Twój prompt.
- Klucz API trzymany lokalnie w EncryptedSharedPreferences (AES-256).

## Co można dodać później
- Gemini Vision: zrzut ekranu → AI widzi co jest na ekranie → autonomiczna
  nawigacja po dowolnej apce ("dodaj te buty do koszyka").
- Allegro REST API (potrzeba klucza developera) — szybsza, dokładniejsza porównywarka.
- Zapis historii i listy życzeń w Room.
