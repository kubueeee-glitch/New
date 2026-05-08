package com.aishop.assistant.control

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import com.aishop.assistant.ai.ControlStep
import kotlinx.coroutines.delay

/**
 * Mapuje aliasy aplikacji na pakiety. Dla nieznanych prób uruchomienia uruchamiamy
 * wyszukanie w Google Play (działa zawsze).
 */
private val APP_PACKAGES = mapOf(
    "youtube" to "com.google.android.youtube",
    "spotify" to "com.spotify.music",
    "whatsapp" to "com.whatsapp",
    "messenger" to "com.facebook.orca",
    "instagram" to "com.instagram.android",
    "facebook" to "com.facebook.katana",
    "tiktok" to "com.zhiliaoapp.musically",
    "allegro" to "pl.allegro",
    "olx" to "pl.tablica",
    "ceneo" to "pl.ceneo",
    "x-kom" to "pl.com.xkom.client",
    "xkom" to "pl.com.xkom.client",
    "media expert" to "com.mediaexpert.app",
    "mediaexpert" to "com.mediaexpert.app",
    "morele" to "pl.morele.android",
    "empik" to "com.empik.empikapp",
    "zalando" to "de.zalando.mobile",
    "google" to "com.google.android.googlequicksearchbox",
    "mapy" to "com.google.android.apps.maps",
    "maps" to "com.google.android.apps.maps",
    "gmail" to "com.google.android.gm",
    "kalendarz" to "com.google.android.calendar",
    "kamera" to "com.google.android.GoogleCamera",
    "chrome" to "com.android.chrome"
)

class ActionExecutor(private val context: Context) {

    fun launchApp(name: String): Boolean {
        val key = name.trim().lowercase()
        val pkg = APP_PACKAGES[key]
            ?: APP_PACKAGES.entries.firstOrNull { key.contains(it.key) }?.value
        if (pkg != null) {
            val intent = context.packageManager.getLaunchIntentForPackage(pkg)
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                return true
            }
        }
        // fallback — Play Store
        val play = Intent(Intent.ACTION_VIEW, Uri.parse("market://search?q=$key")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(play)
        return false
    }

    fun openUrl(url: String) {
        val i = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(i)
    }

    fun openAccessibilitySettings() {
        val i = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(i)
    }

    /**
     * Wykonuje sekwencję kroków przez AccessibilityService. Wymaga włączonej usługi.
     * Zwraca komunikat statusu po polsku.
     */
    suspend fun runSteps(steps: List<ControlStep>): String {
        if (!PhoneControlService.isEnabled()) {
            openAccessibilitySettings()
            return "Włącz najpierw 'AI Shop' w Ustawienia → Dostępność, a potem powtórz."
        }
        val svc = PhoneControlService.instance() ?: return "Brak usługi dostępności."
        for ((i, step) in steps.withIndex()) {
            val ok = when (step.action.uppercase()) {
                "OPEN_APP" -> { step.target?.let { launchApp(it) }; delay(1500); true }
                "CLICK" -> { delay(500); val t = step.target.orEmpty(); svc.clickFirstMatching(t) }
                "TYPE" -> { delay(400); svc.typeIntoFocused(step.text.orEmpty()) }
                "SCROLL_DOWN" -> { delay(300); svc.scrollDown() }
                "SCROLL_UP" -> { delay(300); svc.scrollUp() }
                "BACK" -> svc.goBack()
                "HOME" -> svc.goHome()
                else -> false
            }
            if (!ok) return "Nie udało się: krok ${i + 1} (${step.action} ${step.target ?: step.text ?: ""})"
            delay(700)
        }
        return "Gotowe ✓"
    }
}
