package com.shroudbyte

import android.util.Log
import com.shroudbyte.storage.Storage
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.time.Instant

/**
 * Global crash handler that writes uncaught exceptions to a local file
 * inside the app's private data directory. Mirrors
 * `browser/crashhandler.py` — never uploads, the user can read or copy
 * the file from the About screen.
 */
object CrashLogger {

    private const val MAX_BYTES = 512 * 1024  // same 512 KB cap as desktop

    fun crashLogFile(storage: Storage): File = storage.raw("crash.log")

    /** Install once at process start. */
    fun install(storage: Storage) {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                writeCrash(storage, thread, throwable)
            } catch (_: Throwable) {
                // Last-resort: log to logcat and let the default handler
                // finish killing the process.
                Log.e("Shroudbyte", "Crash logging itself failed", throwable)
            }
            previous?.uncaughtException(thread, throwable)
        }
    }

    private fun writeCrash(storage: Storage, thread: Thread, throwable: Throwable) {
        val file = crashLogFile(storage)
        // Rotate if the existing log is huge.
        if (file.exists() && file.length() > MAX_BYTES) {
            file.renameTo(File(file.parentFile, "crash.log.old"))
        }
        val report = buildString {
            append("--- Crash at ").append(Instant.now()).append(" ---\n")
            append("Thread: ").append(thread.name).append('\n')
            val sw = StringWriter()
            throwable.printStackTrace(PrintWriter(sw))
            append(sw.toString())
            append("---\n\n")
        }
        file.appendText(report, Charsets.UTF_8)
    }
}
