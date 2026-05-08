package com.aishop.assistant.prefs

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class AppPrefs(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(
        context,
        "ai_shop_prefs",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    var geminiKey: String
        get() = prefs.getString("gemini_key", "").orEmpty()
        set(v) { prefs.edit().putString("gemini_key", v).apply() }
}
