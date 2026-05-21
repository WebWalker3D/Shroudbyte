package com.shroudbyte.storage

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Settings file mirroring the keys the desktop client uses where it
 * makes sense on mobile. Anything platform-specific (pfSense DNS,
 * AppImage paths, etc.) is omitted; defaults are documented inline.
 */
@Serializable
data class AppSettings(
    val searchEngine: String = "https://duckduckgo.com/?q={q}",
    val enableJavascript: Boolean = true,
    val enableAdblock: Boolean = true,
    val httpsOnly: Boolean = true,
    val doNotTrack: Boolean = true,
    val stripTracking: Boolean = true,
    val restoreSession: Boolean = true,
    val theme: String = "dark",       // "dark" | "light" | "high_contrast"
    val tabHibernateMinutes: Int = 0, // 0 = off
)

class SettingsRepository(private val storage: Storage) {

    fun load(): AppSettings =
        storage.load(FILE, AppSettings.serializer(), AppSettings())

    fun save(settings: AppSettings) {
        storage.save(FILE, AppSettings.serializer(), settings)
    }

    fun update(transform: (AppSettings) -> AppSettings): AppSettings {
        val next = transform(load())
        save(next)
        return next
    }

    private companion object {
        const val FILE = "settings.json"
    }
}
