# Jarvis — lokalny asystent głosowy

Kamerdyner w stylu SF na jednej maszynie: RTX 3060 Ti (8 GB), 32 GB RAM, Windows.
Całe audio na CPU, GPU wyłącznie dla LLM, budżet VRAM ~7 GB. W spoczynku
niewyczuwalny: 0 MB VRAM, 0% GPU.

## Uruchomienie

```bash
pip install -e .            # albo: uv sync   (zależności z pyproject.toml)
ollama pull qwen3:4b        # L1-fast (~2,5 GB)
ollama pull qwen3.5:9b      # L1-main text-only (~6,6 GB)

python -m jarvis            # pełny asystent głosowy + HUD (http://127.0.0.1:8765)
python -m jarvis --no-hud   # bez panelu
python -m jarvis --text     # tryb tekstowy — bez mikrofonu, do prób na sucho
```

Konfiguracja w jednym miejscu: `jarvis/config.yaml` (modele, ścieżki, limity,
progi trybów, whitelisty akcji, źródła Sentinela, wykluczenia prywatności).

## Etapy (E0–E8) → kod

| etap | co | pliki |
|---|---|---|
| **E0** | scaffold: pyproject, config, CLAUDE.md | `pyproject.toml`, `config.yaml`, `config.py` |
| **E1** | pętla głosowa: wake → VAD → STT → TTS zdaniami, barge-in | `audio/` (`loop.py`, `wake.py`, `vad.py`, `stt.py`, `tts.py`, `mic.py`) |
| **E2** | router L0→L1-fast→L1-main, tryby, watchdog, persona | `llm/` (`router.py`, `modes.py`, `gpu.py`, `ollama.py`, `persona.py`, `cache.py`) |
| **E3** | bus + scheduler (max 3 workery), lazy-loading skilli | `core/`, `skills/` (`time`, `note_add`, `web_search`) |
| **E4** | pamięć: vault Obsidian + indeks FTS5, `recall(q,k)` | `memory/` (`vault.py`, `index.py`) |
| **E5** | sterowanie OS: whitelist, destrukcyjne → potwierdzenie głosem, log | `actions/` (`__init__.py`, `handlers.py`) |
| **E6** | HUD: FastAPI + WebSocket + jeden HTML | `hud/` (`server.py`, `state.py`, `index.html`) |
| **E7** | sentinel: obserwacja, reguły deterministyczne, LLM tylko tłumaczy | `sentinel/` (`collectors.py`, `rules.py`, `translator.py`, `service.py`) |
| **E8** | wzrok: routing S0/S1/S2, menedżer VRAM, prywatność, anty-injection | `vision/` — zob. [`docs/E8-WZROK.md`](docs/E8-WZROK.md) |
| — | orkiestrator spinający całość | `app.py`, `__main__.py` |

## Kluczowe reguły projektu (egzekwowane w kodzie i testach)

- **Nigdy dwa modele w VRAM naraz** — `OllamaClient` zwalnia poprzedni przed
  załadowaniem następnego; przejście do wzroku S2 przez `vision/vram.py`.
- **Tryby**: `sleep`/`listen`/`active`/`gaming` przełączane automatycznie;
  w `sleep` i `gaming` Ollama trzyma 0 MB; watchdog >6,8 GB lub >80°C → sen + głos.
- **Persona**: maksymalnie dwa zdania, zero preambuł — `llm/persona.py` ucina twardo.
- **Akcje wyzwala wyłącznie głos** — tekst z ekranu (E8) i wszystko z Sentinela
  (E7) to DANE, nigdy instrukcje; `ActionGate` odrzuca wyzwalacze nie-głosowe.
- **Prywatność wzroku**: zrzut tylko na komendę głosową, tylko w pamięci,
  lista wykluczeń, do vaulta trafia wyłącznie tekst.

## Testy

```bash
python -m unittest discover -s jarvis/tests -t .
```

96 testów, działają bez GPU/mikrofonu/Ollamy (komponenty sprzętowe zastępują
atrapy). Test zaliczeniowy E8 (odporność na prompt injection z ekranu):
`tests/test_e8_injection_acceptance.py`. Test spięcia całości:
`tests/test_app_integration.py`.
