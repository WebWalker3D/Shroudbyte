package com.shroudbyte.watches

import com.shroudbyte.storage.Storage
import java.security.MessageDigest
import java.util.UUID
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer

/**
 * Background page-change monitor. Mirrors `browser/pagewatcher.py`.
 *
 * A "watch" is a URL the user wants Shroudbyte to keep an eye on.
 * The worker fetches each watched URL periodically, hashes the body,
 * and posts a notification when the hash changes.
 *
 * Persisted as a JSON file so the WorkManager job can read it from a
 * fresh process after a reboot without bootstrapping the whole app.
 */
@Serializable
data class PageWatch(
    val id: String,
    val url: String,
    val title: String,
    /** Minutes between fetches. */
    val intervalMinutes: Int = 60,
    /** SHA-256 of the last body we successfully fetched, hex-encoded. */
    val lastHash: String = "",
    /** Unix-seconds timestamp of the last successful fetch. */
    val lastCheckedAt: Double = 0.0,
    /** Unix-seconds timestamp of the last detected change. */
    val lastChangedAt: Double = 0.0,
    /** Most recent body excerpt, capped to keep the file small. */
    val lastSnippet: String = "",
)

class PageWatchesRepository(private val storage: Storage) {

    private val serializer = ListSerializer(PageWatch.serializer())

    fun all(): List<PageWatch> = storage.load(FILE, serializer, emptyList())

    fun add(url: String, title: String, intervalMinutes: Int = 60): PageWatch {
        val current = all().toMutableList()
        // Same URL stays unique — adding twice just refreshes the title.
        val existing = current.indexOfFirst { it.url == url }
        if (existing >= 0) {
            current[existing] = current[existing].copy(title = title)
            storage.save(FILE, serializer, current)
            return current[existing]
        }
        val w = PageWatch(
            id = UUID.randomUUID().toString(),
            url = url,
            title = title.ifBlank { url },
            intervalMinutes = intervalMinutes.coerceAtLeast(5),
        )
        current += w
        storage.save(FILE, serializer, current)
        return w
    }

    fun remove(id: String): Boolean {
        val current = all()
        val filtered = current.filterNot { it.id == id }
        if (filtered.size == current.size) return false
        storage.save(FILE, serializer, filtered)
        return true
    }

    fun update(updated: PageWatch) {
        val current = all().toMutableList()
        val idx = current.indexOfFirst { it.id == updated.id }
        if (idx < 0) return
        current[idx] = updated
        storage.save(FILE, serializer, current)
    }

    fun setInterval(id: String, minutes: Int) {
        val current = all().toMutableList()
        val idx = current.indexOfFirst { it.id == id }
        if (idx < 0) return
        current[idx] = current[idx].copy(intervalMinutes = minutes.coerceAtLeast(5))
        storage.save(FILE, serializer, current)
    }

    private companion object {
        const val FILE = "watches.json"
    }
}

/**
 * Helpers shared between the foreground UI and the background worker.
 */
object PageWatchOps {

    fun hash(body: ByteArray): String {
        val md = MessageDigest.getInstance("SHA-256")
        val digest = md.digest(body)
        return digest.joinToString("") { "%02x".format(it) }
    }

    /** Crude but deterministic body excerpt for the dashboard preview. */
    fun snippet(body: String, max: Int = 240): String {
        val text = body
            .replace(Regex("<script[\\s\\S]*?</script>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("<style[\\s\\S]*?</style>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("<[^>]+>"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
        return if (text.length <= max) text else text.take(max) + "…"
    }
}
