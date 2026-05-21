package com.shroudbyte.watches

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.shroudbyte.MainActivity
import com.shroudbyte.ShroudApplication
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Periodic worker that hashes every watched page and posts a notification
 * if the hash changed since the last successful check.
 *
 * Scheduled by [PageWatchScheduler]. Mirrors the polling loop in
 * `browser/pagewatcher.py`. We use HEAD when the body would be too
 * large or the server supports it cheaply, but fall back to a GET
 * since some sites give back useless 200s on HEAD.
 */
class PageWatchWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val app = applicationContext as ShroudApplication
        val repo = PageWatchesRepository(app.storage)
        val now = System.currentTimeMillis() / 1000.0
        val watches = repo.all()
        val due = watches.filter {
            // First-ever fetch fires; subsequent fetches respect interval.
            it.lastCheckedAt == 0.0 ||
                now - it.lastCheckedAt >= it.intervalMinutes * 60
        }
        for (w in due) {
            try {
                val body = fetch(w.url) ?: continue
                val hash = PageWatchOps.hash(body.toByteArray(Charsets.UTF_8))
                val changed = w.lastHash.isNotEmpty() && hash != w.lastHash
                val updated = w.copy(
                    lastHash = hash,
                    lastCheckedAt = now,
                    lastChangedAt = if (changed) now else w.lastChangedAt,
                    lastSnippet = PageWatchOps.snippet(body),
                )
                repo.update(updated)
                if (changed) postChangeNotification(updated)
            } catch (_: Exception) {
                // Network errors are normal — try again next pass.
            }
        }
        Result.success()
    }

    private fun fetch(url: String): String? {
        val conn = (URL(url).openConnection() as? HttpURLConnection) ?: return null
        try {
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "Shroudbyte-Watcher/1.0")
            // Cap downloaded bytes so a runaway response can't OOM us.
            val limit = 256 * 1024
            return conn.inputStream.use { stream ->
                val out = StringBuilder()
                val buf = ByteArray(4096)
                var total = 0
                while (true) {
                    val n = stream.read(buf)
                    if (n <= 0) break
                    out.append(String(buf, 0, n))
                    total += n
                    if (total >= limit) break
                }
                out.toString()
            }
        } finally {
            conn.disconnect()
        }
    }

    private fun postChangeNotification(w: PageWatch) {
        val ctx = applicationContext
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL, "Page changes",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "Notified when a watched page changes."
                }
            )
        }
        // Tapping the notification opens the URL in Shroudbyte.
        val intent = Intent(ctx, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            data = Uri.parse(w.url)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = PendingIntent.getActivity(
            ctx, w.id.hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notif: Notification = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Page changed: ${w.title}")
            .setContentText(w.url)
            .setStyle(NotificationCompat.BigTextStyle()
                .bigText(w.lastSnippet.take(200)))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        nm.notify(w.id.hashCode(), notif)
    }

    private companion object {
        const val CHANNEL = "page_changes"
    }
}
