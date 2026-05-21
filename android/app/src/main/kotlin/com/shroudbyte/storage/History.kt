package com.shroudbyte.storage

import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer

@Serializable
data class HistoryEntry(
    val url: String,
    val title: String,
    val visitedAt: Double,
)

/**
 * Append-only browsing history with a soft cap. The desktop client uses
 * SQLite for this; on Android we start with a JSON file capped at
 * [MAX_ENTRIES] entries — well under what causes any disk pressure — and
 * can migrate to Room later if the size becomes a problem.
 */
class HistoryRepository(private val storage: Storage) {

    private val serializer = ListSerializer(HistoryEntry.serializer())

    fun load(): List<HistoryEntry> =
        storage.load(FILE, serializer, emptyList())

    fun record(url: String, title: String) {
        if (url.isBlank() || url.startsWith("about:") || url.startsWith("shroud:")) return
        val current = load().toMutableList()
        // De-duplicate the most-recent entry so an F5 doesn't double-record.
        if (current.lastOrNull()?.url == url) {
            current[current.lastIndex] = current.last().copy(
                title = title,
                visitedAt = System.currentTimeMillis() / 1000.0,
            )
        } else {
            current += HistoryEntry(
                url = url,
                title = title,
                visitedAt = System.currentTimeMillis() / 1000.0,
            )
        }
        // Soft cap: drop the oldest entries when over the limit.
        val trimmed = if (current.size > MAX_ENTRIES) {
            current.subList(current.size - MAX_ENTRIES, current.size).toList()
        } else current.toList()
        storage.save(FILE, serializer, trimmed)
    }

    fun clear() {
        storage.save(FILE, serializer, emptyList())
    }

    fun search(query: String, limit: Int = 50): List<HistoryEntry> {
        val q = query.lowercase()
        return load().asReversed().asSequence()
            .filter { it.url.lowercase().contains(q) || it.title.lowercase().contains(q) }
            .take(limit)
            .toList()
    }

    private companion object {
        const val FILE = "history.json"
        const val MAX_ENTRIES = 5000
    }
}
