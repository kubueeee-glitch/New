"""Pipeline wzroku (E8): „hej, zobacz to" → zrzut → odpowiedź.

Kolejność twardych reguł:
1. Wyzwalaczem jest WYŁĄCZNIE głos (Trigger.source == VOICE) — nic z ekranu,
   nic z systemu nie może zainicjować zrzutu ani akcji.
2. Okno z listy wykluczeń → odmowa zrzutu + komunikat głosowy.
3. Zrzut żyje tylko w pamięci i jest zerowany po odpowiedzi; zapis na dysk
   wyłącznie po jawnym „zapisz to".
4. Treść ekranu idzie do promptu tylko w bloku <screen_content> jako DANE.
5. Pipeline nie ma żadnej ścieżki do `actions/` — strukturalnie nie może
   wywołać akcji na podstawie tego, co przeczytał z ekranu.
6. S2 nie zmieści się w celu 800 ms: natychmiast mówimy „Patrzę." z lokalnego
   TTS, potem odpowiadamy — cisza przez 6 s wygląda jak zawieszenie.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

from .capture import ScreenCapture, save_png
from .privacy import PrivacyGuard
from .router import VisionRouter
from .s0_uia import read_active_window_text
from .s1_ocr import OcrEngine
from .s2_vlm import VlmClient
from .sanitize import build_screen_prompt
from .types import CaptureScope, Trigger, TriggerSource, VisionLevel, VisionResult

# Poniżej tylu znaków uznajemy, że S0/S1 nic nie widzą — eskalacja do S2.
MIN_TEXT_CHARS = 12

ACK_S2 = "Patrzę."
REFUSAL_NOT_VOICE = "Zrzut ekranu wyzwala wyłącznie jawna komenda głosowa."


class VisionPipeline:
    def __init__(
        self,
        *,
        capture: ScreenCapture,
        ocr: OcrEngine,
        vlm: VlmClient,
        llm_answer: Callable[[str, str], str],
        speak: Callable[[str], None] = lambda text: None,
        guard: Optional[PrivacyGuard] = None,
        router: Optional[VisionRouter] = None,
        s0_reader: Callable[[], Optional[str]] = read_active_window_text,
        vault_store: Optional[Callable[[str], None]] = None,
        save_dir: str = ".",
    ) -> None:
        self.capture = capture
        self.ocr = ocr
        self.vlm = vlm
        self.llm_answer = llm_answer
        self.speak = speak
        self.guard = guard or PrivacyGuard()
        self.router = router or VisionRouter()
        self.s0_reader = s0_reader
        self.vault_store = vault_store
        self.save_dir = save_dir

    def handle(
        self,
        question: str,
        trigger: Trigger,
        *,
        scope: CaptureScope = CaptureScope.ACTIVE_WINDOW,
        monitor_index: int = 2,
        save_requested: bool = False,
    ) -> VisionResult:
        if not isinstance(trigger, Trigger) or trigger.source is not TriggerSource.VOICE:
            return VisionResult(
                answer="",
                level=None,
                refused=True,
                refusal_reason=REFUSAL_NOT_VOICE,
            )

        title = self.capture.active_window_title()
        if self.guard.is_excluded(title):
            self.speak(PrivacyGuard.SPOKEN_REFUSAL)
            return VisionResult(
                answer=PrivacyGuard.SPOKEN_REFUSAL,
                level=None,
                refused=True,
                refusal_reason="excluded_window",
            )

        shot = self.capture.grab(scope, monitor_index)
        saved_to = ""
        try:
            level = self.router.choose_level(question)
            if level is VisionLevel.S2:
                answer, model, level = self._answer_s2(question, shot)
            else:
                answer, model, level = self._answer_text(question, shot, scope)
            if save_requested:
                saved_to = self._save(shot)
        finally:
            shot.wipe()

        if self.vault_store is not None:
            # Do vaulta trafia tekstowe streszczenie, nigdy obraz.
            self.vault_store(f"[wzrok:{level.value}] {question} → {answer[:300]}")

        return VisionResult(answer=answer, level=level, model=model, saved_to=saved_to)

    def _answer_text(self, question, shot, scope) -> tuple[str, str, VisionLevel]:
        screen_text = None
        level = VisionLevel.S0
        if scope is CaptureScope.ACTIVE_WINDOW:
            # S0 jest dokładniejszy od OCR dla aplikacji natywnych — zawsze pierwszy.
            screen_text = self.s0_reader()
        if not screen_text or len(screen_text.strip()) < MIN_TEXT_CHARS:
            screen_text = self.ocr.read(shot)
            level = VisionLevel.S1
        if not screen_text or len(screen_text.strip()) < MIN_TEXT_CHARS:
            return self._answer_s2(question, shot)
        system, user = build_screen_prompt(question, screen_text)
        return self.llm_answer(system, user), "", level

    def _answer_s2(self, question, shot) -> tuple[str, str, VisionLevel]:
        self.speak(ACK_S2)
        answer, model = self.vlm.answer(question, shot)
        return answer, model, VisionLevel.S2

    def _save(self, shot) -> str:
        os.makedirs(self.save_dir, exist_ok=True)
        path = os.path.join(
            self.save_dir, time.strftime("jarvis-zrzut-%Y%m%d-%H%M%S.png")
        )
        return save_png(shot, path)
