package com.shroudbyte.browser

import com.shroudbyte.storage.Storage
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer

/**
 * Tab session save / restore — mirrors `browser/mixins/session.py`.
 *
 * Internal `shroud://` URLs aren't restored (mobile doesn't have those
 * yet); blank tabs aren't either, so a normal first-run state is empty.
 */
@Serializable
data class SavedTab(val url: String, val title: String)

class SessionRepository(private val storage: Storage) {

    private val serializer = ListSerializer(SavedTab.serializer())

    fun save(tabs: List<TabState>) {
        val payload = tabs
            .filter { it.url.isNotBlank() && it.url != "about:blank" }
            .map { SavedTab(it.url, it.title) }
        storage.save(FILE, serializer, payload)
    }

    fun load(): List<SavedTab> =
        storage.load(FILE, serializer, emptyList())

    fun clear() {
        storage.save(FILE, serializer, emptyList())
    }

    private companion object {
        const val FILE = "session.json"
    }
}
