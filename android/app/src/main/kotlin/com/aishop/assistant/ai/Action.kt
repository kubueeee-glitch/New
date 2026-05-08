package com.aishop.assistant.ai

import kotlinx.serialization.Serializable

/**
 * Wynik parsowania promptu przez Gemini. Apka mapuje to na konkretne akcje:
 *  - SEARCH_SHOPS: otwiera wyszukiwania w sklepach + porównywarkę cen
 *  - OPEN_APP: uruchamia aplikację po nazwie (np. "youtube", "spotify")
 *  - PHONE_CONTROL: sekwencja kroków dla AccessibilityService (klik/scroll/wpis)
 *  - WEB_SEARCH: zwykłe wyszukiwanie w Google
 *  - ANSWER: odpowiedź tekstowa, gdy AI nie potrzebuje akcji
 */
@Serializable
data class ParsedIntent(
    val type: String,
    val query: String? = null,
    val maxPrice: Double? = null,
    val minPrice: Double? = null,
    val shops: List<String> = emptyList(),
    val appName: String? = null,
    val steps: List<ControlStep> = emptyList(),
    val answer: String? = null
)

@Serializable
data class ControlStep(
    val action: String,
    val target: String? = null,
    val text: String? = null
)
