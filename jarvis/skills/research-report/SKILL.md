---
name: Raport z researchu
description: Gdy użytkownik prosi o zbadanie tematu — zrób wieloźródłowy research i zapisz ustrukturyzowany raport do bazy wiedzy.
---

# Raport z researchu

Użyj, gdy użytkownik chce dogłębnie zbadać jakiś temat.

## Procedura
1. Sprawdź `read_topic`, czy tematu nie ma już w bazie wiedzy — jeśli jest, buduj na nim (pogłębianie).
2. Wykonaj 2–4 zapytania `web_search` z różnych stron (definicje, aktualne dane, opinie/porównania).
3. Zsyntetyzuj wynik w strukturze:
   - **Podsumowanie** (3–5 zdań)
   - **Kluczowe fakty** (punkty)
   - **Za i przeciw / porównanie** (jeśli dotyczy)
   - **Źródła** (lista URL)
4. Zapisz przez `save_topic` (nazwa = temat). Zawsze dołącz źródła.
5. Użytkownikowi podaj krótkie wnioski + informację, że pełny raport wylądował w bazie wiedzy.

## Zasady
- Cytuj źródła, nie zmyślaj. Gdy dane są niepewne — powiedz to wprost.
- Preferuj świeże informacje (bieżący rok).
