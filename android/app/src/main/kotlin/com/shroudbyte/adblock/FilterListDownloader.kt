package com.shroudbyte.adblock

import android.util.Log
import com.shroudbyte.storage.Storage
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer

/**
 * Downloads enabled filter lists, parses them into host sets, and
 * caches the combined result on disk so subsequent app starts can pick
 * the hosts up without a network round-trip.
 *
 * Refresh policy mirrors the desktop client: a fetch is considered
 * fresh for 24 hours.
 */
@Serializable
data class FilterListMeta(
    val sourceId: String,
    val fetchedAt: Double,
    val hostCount: Int,
)

class FilterListDownloader(
    private val storage: Storage,
    private val prefs: FilterListPreferences,
    private val sources: List<FilterListSource> = FilterLists.SOURCES,
) {

    private val metaSerializer = ListSerializer(FilterListMeta.serializer())

    /**
     * Read the cached combined host set off disk. Used at app startup
     * so HostBlocker has something to work with before the first
     * network refresh completes.
     */
    fun loadCached(): Set<String> {
        val file = cacheFile()
        if (!file.exists()) return emptySet()
        return file.readLines(Charsets.UTF_8)
            .asSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() && !it.startsWith('#') }
            .toSet()
    }

    /** Combined host count last cached. */
    fun lastFetched(): List<FilterListMeta> =
        storage.load(META_FILE, metaSerializer, emptyList())

    fun lastRefreshAt(): Double =
        lastFetched().maxOfOrNull { it.fetchedAt } ?: 0.0

    fun needsRefresh(): Boolean {
        val last = lastRefreshAt()
        if (last == 0.0) return true
        val now = System.currentTimeMillis() / 1000.0
        return (now - last) > REFRESH_INTERVAL_SECONDS
    }

    /**
     * Download every enabled list and write a unified host set to the
     * cache file. Returns the combined host set the caller can hand
     * to HostBlocker.setHosts(). Synchronous; call from a worker.
     */
    fun refresh(): Set<String> {
        val combined = HashSet<String>()
        val metas = mutableListOf<FilterListMeta>()
        val now = System.currentTimeMillis() / 1000.0

        for (source in sources) {
            if (!prefs.isEnabled(source)) continue
            try {
                val text = fetch(source.url) ?: continue
                val hosts = when (source.format) {
                    FilterListFormat.HOSTS -> FilterListParser.parseHosts(text)
                    FilterListFormat.ABP -> FilterListParser.parseAbp(text)
                }
                metas += FilterListMeta(source.id, now, hosts.size)
                combined += hosts
            } catch (e: Exception) {
                Log.w("Shroudbyte/FL", "Failed to fetch ${source.id}: ${e.message}")
            }
        }

        // Persist a compact one-host-per-line cache.
        cacheFile().writeText(combined.sorted().joinToString("\n"), Charsets.UTF_8)
        storage.save(META_FILE, metaSerializer, metas)
        return combined
    }

    private fun fetch(url: String): String? {
        val conn = (URL(url).openConnection() as? HttpURLConnection) ?: return null
        try {
            conn.connectTimeout = 15_000
            conn.readTimeout = 30_000
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "Shroudbyte/1.0 (filter-list)")
            if (conn.responseCode !in 200..299) return null
            // Hosts files can be a few MB; cap to a sane upper bound.
            val limit = 16 * 1024 * 1024
            return conn.inputStream.use { stream ->
                val out = StringBuilder()
                val buf = ByteArray(8192)
                var total = 0
                while (true) {
                    val n = stream.read(buf)
                    if (n <= 0) break
                    out.append(String(buf, 0, n, Charsets.UTF_8))
                    total += n
                    if (total >= limit) break
                }
                out.toString()
            }
        } finally {
            conn.disconnect()
        }
    }

    private fun cacheFile(): File = storage.raw(CACHE_FILE)

    private companion object {
        const val CACHE_FILE = "filter_hosts.txt"
        const val META_FILE = "filter_meta.json"
        const val REFRESH_INTERVAL_SECONDS = 24.0 * 3600.0
    }
}
