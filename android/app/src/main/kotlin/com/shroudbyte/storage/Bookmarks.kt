package com.shroudbyte.storage

import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer

/**
 * Bookmark CRUD layer mirroring the desktop `storage.add_bookmark` /
 * `load_bookmarks` API. The on-disk JSON file is named `bookmarks.json`
 * with the same field names as the desktop client so a future cross-
 * platform import can read it directly.
 */
@Serializable
data class Bookmark(
    val title: String,
    val url: String,
    val added: Double = 0.0,
    val folder: String = "",
    val tags: List<String> = emptyList(),
)

class BookmarksRepository(private val storage: Storage) {

    private val serializer = ListSerializer(Bookmark.serializer())

    fun all(): List<Bookmark> =
        storage.load(FILE, serializer, emptyList())

    /** Add a bookmark unless its URL already exists. Returns true if inserted. */
    fun add(title: String, url: String, folder: String = "",
            tags: List<String> = emptyList()): Boolean {
        val current = all().toMutableList()
        if (current.any { it.url == url }) return false
        current += Bookmark(
            title = title.ifBlank { url },
            url = url,
            added = System.currentTimeMillis() / 1000.0,
            folder = folder,
            tags = tags,
        )
        storage.save(FILE, serializer, current)
        return true
    }

    fun remove(url: String) {
        val filtered = all().filterNot { it.url == url }
        storage.save(FILE, serializer, filtered)
    }

    fun isBookmarked(url: String): Boolean = all().any { it.url == url }

    /** Reorder by URL list — URLs absent from [order] keep their original tail position. */
    fun reorder(order: List<String>) {
        val byUrl = all().associateBy { it.url }
        val seen = mutableSetOf<String>()
        val out = mutableListOf<Bookmark>()
        for (u in order) {
            val bm = byUrl[u]
            if (bm != null && seen.add(u)) out += bm
        }
        // Append unmoved bookmarks in original order.
        for (bm in all()) {
            if (seen.add(bm.url)) out += bm
        }
        storage.save(FILE, serializer, out)
    }

    private companion object {
        const val FILE = "bookmarks.json"
    }
}
