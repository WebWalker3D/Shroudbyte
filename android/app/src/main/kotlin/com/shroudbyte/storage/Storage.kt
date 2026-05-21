package com.shroudbyte.storage

import android.content.Context
import java.io.File
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json

/**
 * Filesystem-backed JSON store. Mirrors `browser/storage.py` — every
 * call lives under a single [dataDir] (the app's private filesDir on
 * Android), and missing files return the supplied default rather than
 * raising.
 *
 * Intentionally synchronous; the data is small enough that the
 * disk-time cost is negligible. Wrap calls in `withContext(Dispatchers.IO)`
 * when invoked from the UI thread.
 */
class Storage(val dataDir: File) {

    init {
        if (!dataDir.exists()) dataDir.mkdirs()
    }

    private val json = Json {
        ignoreUnknownKeys = true   // Forward-compat: old apks won't crash on new fields.
        prettyPrint = false
    }

    fun <T> load(filename: String, serializer: KSerializer<T>, default: T): T {
        val file = File(dataDir, filename)
        if (!file.exists()) return default
        return try {
            json.decodeFromString(serializer, file.readText(Charsets.UTF_8))
        } catch (_: Exception) {
            default
        }
    }

    fun <T> save(filename: String, serializer: KSerializer<T>, value: T) {
        val tmp = File(dataDir, "$filename.tmp")
        tmp.writeText(json.encodeToString(serializer, value), Charsets.UTF_8)
        // Atomic-ish replace: rename is single-syscall on the same FS.
        if (!tmp.renameTo(File(dataDir, filename))) {
            // Fallback for filesystems where renameTo can fail.
            File(dataDir, filename).writeText(
                json.encodeToString(serializer, value), Charsets.UTF_8
            )
            tmp.delete()
        }
    }

    fun raw(filename: String): File = File(dataDir, filename)

    companion object {
        /** Default Storage rooted at the app's private files directory. */
        fun forContext(ctx: Context): Storage = Storage(ctx.filesDir)
    }
}
