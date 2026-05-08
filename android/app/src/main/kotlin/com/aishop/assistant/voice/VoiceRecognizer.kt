package com.aishop.assistant.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.util.Locale

class VoiceRecognizer(private val context: Context) {

    private var recognizer: SpeechRecognizer? = null

    fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    fun start(
        onPartial: (String) -> Unit = {},
        onResult: (String) -> Unit,
        onError: (String) -> Unit = {}
    ) {
        stop()
        val r = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = r
        r.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(p0: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(p0: Float) {}
            override fun onBufferReceived(p0: ByteArray?) {}
            override fun onEndOfSpeech() {}

            override fun onError(code: Int) {
                onError(errorMessage(code))
            }

            override fun onResults(bundle: Bundle?) {
                val list = bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                onResult(list?.firstOrNull().orEmpty())
            }

            override fun onPartialResults(bundle: Bundle?) {
                val list = bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                list?.firstOrNull()?.let(onPartial)
            }

            override fun onEvent(p0: Int, p1: Bundle?) {}
        })

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale("pl", "PL").toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "pl-PL")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        r.startListening(intent)
    }

    fun stop() {
        recognizer?.stopListening()
        recognizer?.destroy()
        recognizer = null
    }

    private fun errorMessage(code: Int): String = when (code) {
        SpeechRecognizer.ERROR_AUDIO -> "Błąd nagrywania audio"
        SpeechRecognizer.ERROR_CLIENT -> "Błąd klienta"
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Brak uprawnień do mikrofonu"
        SpeechRecognizer.ERROR_NETWORK -> "Brak sieci"
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Timeout sieci"
        SpeechRecognizer.ERROR_NO_MATCH -> "Nic nie usłyszałem"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Rozpoznawanie zajęte"
        SpeechRecognizer.ERROR_SERVER -> "Błąd serwera rozpoznawania"
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Cisza — spróbuj ponownie"
        else -> "Nieznany błąd ($code)"
    }
}
