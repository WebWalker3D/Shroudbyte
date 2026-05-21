package com.shroudbyte.adblock

import com.shroudbyte.storage.Storage
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.serializer

/**
 * Catalogue of downloadable filter lists. The desktop client supports
 * many more; we ship a small starter set whose formats we can parse
 * with the in-process [FilterListParser] without bringing in a real
 * ABP engine.
 *
 *  - hosts: classic `0.0.0.0 example.com` per line
 *  - abp:   subset of ABP — only `||example.com^` and `||example.com^$flags`
 *           rules contribute hosts. Anything fancier is skipped.
 */
enum class FilterListFormat { HOSTS, ABP }

@Serializable
data class FilterListSource(
    val id: String,
    val name: String,
    val url: String,
    val format: FilterListFormat,
    /** Enabled out of the box for new installs. */
    val defaultEnabled: Boolean,
)

object FilterLists {
    val SOURCES: List<FilterListSource> = listOf(
        FilterListSource(
            id = "stevenblack",
            name = "StevenBlack unified hosts",
            url = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
            format = FilterListFormat.HOSTS,
            defaultEnabled = true,
        ),
        FilterListSource(
            id = "peter_lowe",
            name = "Peter Lowe's Ad Server List",
            url = "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext",
            format = FilterListFormat.HOSTS,
            defaultEnabled = true,
        ),
        FilterListSource(
            id = "urlhaus",
            name = "URLhaus Malicious Hosts",
            url = "https://urlhaus.abuse.ch/downloads/hostfile/",
            format = FilterListFormat.HOSTS,
            defaultEnabled = true,
        ),
        FilterListSource(
            id = "easyprivacy",
            name = "EasyPrivacy",
            url = "https://easylist.to/easylist/easyprivacy.txt",
            format = FilterListFormat.ABP,
            defaultEnabled = true,
        ),
        FilterListSource(
            id = "easylist",
            name = "EasyList",
            url = "https://easylist.to/easylist/easylist.txt",
            format = FilterListFormat.ABP,
            defaultEnabled = false,
        ),
    )
}

/**
 * Per-source enable/disable state.
 */
class FilterListPreferences(private val storage: Storage) {

    private val serializer = MapSerializer(String.serializer(), Boolean.serializer())

    private fun load(): Map<String, Boolean> =
        storage.load(FILE, serializer, emptyMap())

    fun isEnabled(source: FilterListSource): Boolean {
        val store = load()
        return store[source.id] ?: source.defaultEnabled
    }

    fun setEnabled(source: FilterListSource, enabled: Boolean) {
        val next = load().toMutableMap()
        next[source.id] = enabled
        storage.save(FILE, serializer, next)
    }

    private companion object {
        const val FILE = "filter_prefs.json"
    }
}

/**
 * Pure parsers for the two formats. Surface-level only — we only
 * recognise rules that contribute *pure* host names, since [HostBlocker]
 * is host-keyed.
 */
object FilterListParser {

    /** Parse a hosts file. Skips comments, IPv6, localhost, broadcast. */
    fun parseHosts(text: String): Set<String> {
        val out = HashSet<String>()
        for (raw in text.lineSequence()) {
            val line = raw.substringBefore('#').trim()
            if (line.isEmpty()) continue
            val parts = line.split(Regex("\\s+"))
            // Format: `<ip> <host>`. We accept either the entry-only
            // form (some lists ship that), or the two-column form.
            val host = when {
                parts.size >= 2 -> parts[1]
                parts.size == 1 -> parts[0]
                else -> continue
            }.lowercase()
            if (host.isBlank()) continue
            if (host == "localhost" || host == "broadcasthost") continue
            if (!host.looksLikeDomain()) continue
            out += host
        }
        return out
    }

    /** Parse an ABP-style file. Pulls pure-host `||example.com^` rules. */
    fun parseAbp(text: String): Set<String> {
        val out = HashSet<String>()
        // Rule shape: optional whitespace, then ||host[^|$|nothing]
        // (anything after that is options we don't model).
        val rx = Regex("""^\|\|([a-z0-9._-]+)\^""", RegexOption.IGNORE_CASE)
        for (raw in text.lineSequence()) {
            val line = raw.trim()
            if (line.isEmpty()) continue
            // ABP comments and metadata
            if (line.startsWith('!') || line.startsWith('[')) continue
            // Exception rule — out of scope for the host blocker.
            if (line.startsWith("@@")) continue
            // Cosmetic / scriptlet — only the network rules concern us.
            if ("##" in line || "#@#" in line || "#?#" in line) continue
            val m = rx.find(line) ?: continue
            val host = m.groupValues[1].lowercase()
            if (host.looksLikeDomain()) out += host
        }
        return out
    }

    private fun String.looksLikeDomain(): Boolean {
        if (length < 4 || '.' !in this) return false
        if (any { it == ' ' || it == '/' }) return false
        // Reject pure-IP entries; HostBlocker matches by name only.
        if (all { it.isDigit() || it == '.' }) return false
        return true
    }
}
