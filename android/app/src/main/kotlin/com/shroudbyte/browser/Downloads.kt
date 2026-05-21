package com.shroudbyte.browser

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.webkit.CookieManager
import android.webkit.URLUtil
import android.webkit.WebView

/**
 * Hand off URLs that the WebView can't render directly (file downloads)
 * to Android's DownloadManager. Mirrors the role of `browser/downloads.py`
 * but defers the actual file copy to the OS — no need to roll our own
 * pause/resume/progress UI.
 *
 * Hook this up via `webView.setDownloadListener { ... }` in the WebView
 * factory.
 */
object Downloads {

    fun enqueue(
        context: Context,
        url: String,
        userAgent: String?,
        contentDisposition: String?,
        mimeType: String?,
    ) {
        val filename = URLUtil.guessFileName(url, contentDisposition, mimeType)
        val request = DownloadManager.Request(Uri.parse(url)).apply {
            setMimeType(mimeType)
            // Inject the WebView's cookies so authenticated downloads work.
            val cookies = CookieManager.getInstance().getCookie(url)
            if (!cookies.isNullOrBlank()) addRequestHeader("Cookie", cookies)
            if (!userAgent.isNullOrBlank()) addRequestHeader("User-Agent", userAgent)
            setDescription("Shroudbyte download")
            setTitle(filename)
            setNotificationVisibility(
                DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
            )
            setDestinationInExternalPublicDir(
                Environment.DIRECTORY_DOWNLOADS, filename
            )
            // Don't index the file into the system Media store — a privacy
            // browser shouldn't be quietly populating gallery indexes.
            setAllowedOverMetered(true)
            setAllowedOverRoaming(true)
        }
        val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        dm.enqueue(request)
    }
}
