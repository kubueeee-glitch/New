package com.aishop.assistant.ai

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class GeminiClient(private val apiKey: String) {

    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    suspend fun parsePrompt(userPrompt: String): ParsedIntent = withContext(Dispatchers.IO) {
        val systemInstruction = """
            Jesteś asystentem AI sterującym telefonem Android i sklepami online w Polsce.
            Zwracasz WYŁĄCZNIE poprawny JSON pasujący do schematu — bez komentarzy, bez markdown.

            Schemat:
            {
              "type": "SEARCH_SHOPS" | "OPEN_APP" | "PHONE_CONTROL" | "WEB_SEARCH" | "ANSWER",
              "query": string?,           // czego szuka użytkownik (zwięźle, bez ceny i sklepu)
              "maxPrice": number?,        // PLN, jeśli wspomniana
              "minPrice": number?,
              "shops": string[],          // identyfikatory: allegro, olx, ceneo, xkom, mediaexpert, morele, empik, zalando, google
              "appName": string?,         // dla OPEN_APP, np. "youtube", "spotify", "whatsapp", "instagram", "tiktok"
              "steps": [                  // dla PHONE_CONTROL — sekwencja kroków
                {"action":"OPEN_APP"|"CLICK"|"TYPE"|"SCROLL_DOWN"|"SCROLL_UP"|"BACK"|"HOME","target":string?,"text":string?}
              ],
              "answer": string?           // dla ANSWER — odpowiedź po polsku
            }

            Zasady:
            - Jeśli użytkownik chce kupić/szukać produkt → SEARCH_SHOPS, wypełnij query, maxPrice, shops (puste = wszystkie).
            - Jeśli mówi "otwórz X", "włącz X" gdzie X to apka → OPEN_APP.
            - Jeśli zlecenie wymaga klikania w obcej apce ("wyślij wiadomość do Maćka na WhatsApp", "puść playlist X w Spotify") → PHONE_CONTROL z krokami. action=CLICK ma 'target' = widoczny tekst przycisku/elementu, action=TYPE ma 'text'. Pierwszy krok zwykle OPEN_APP.
            - Jeśli to ogólne pytanie/wiedza → ANSWER.
            - W razie wątpliwości → WEB_SEARCH.
            - Zwracaj sam JSON, nic poza nim.
        """.trimIndent()

        val req = GeminiRequest(
            systemInstruction = Content(parts = listOf(Part(text = systemInstruction))),
            contents = listOf(Content(role = "user", parts = listOf(Part(text = userPrompt)))),
            generationConfig = GenerationConfig(
                temperature = 0.2,
                responseMimeType = "application/json"
            )
        )

        val body = json.encodeToString(req).toRequestBody("application/json".toMediaType())
        val url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$apiKey"

        val response = http.newCall(Request.Builder().url(url).post(body).build()).execute()
        response.use { r ->
            val raw = r.body?.string().orEmpty()
            if (!r.isSuccessful) throw RuntimeException("Gemini ${r.code}: $raw")
            val parsed = json.decodeFromString<GeminiResponse>(raw)
            val text = parsed.candidates?.firstOrNull()
                ?.content?.parts?.firstOrNull()?.text
                ?: throw RuntimeException("Gemini: pusta odpowiedź")
            json.decodeFromString<ParsedIntent>(text)
        }
    }

    @Serializable
    private data class GeminiRequest(
        val systemInstruction: Content? = null,
        val contents: List<Content>,
        val generationConfig: GenerationConfig? = null
    )

    @Serializable
    private data class Content(val role: String? = null, val parts: List<Part>)

    @Serializable
    private data class Part(val text: String)

    @Serializable
    private data class GenerationConfig(
        val temperature: Double? = null,
        val responseMimeType: String? = null
    )

    @Serializable
    private data class GeminiResponse(val candidates: List<Candidate>? = null)

    @Serializable
    private data class Candidate(val content: Content? = null)
}
