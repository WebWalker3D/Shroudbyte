package com.shroudbyte.browser

import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import com.shroudbyte.adblock.HostBlocker
import com.shroudbyte.adblock.TrackingParams
import com.shroudbyte.storage.HistoryRepository
import com.shroudbyte.storage.SettingsRepository
import java.io.ByteArrayInputStream

/**
 * WebView client with the same defensive behaviours as
 * `browser/adblock.py` on desktop:
 *
 *  - Drop subresource requests to known tracker hosts.
 *  - Rewrite outgoing main-frame URLs to strip utm_ params, fbclid, and friends.
 *  - Upgrade plain http:// to https:// when HTTPS-only mode is on.
 *  - Record the URL we end up on in the history store.
 */
class ShroudWebViewClient(
    private val tab: TabState,
    private val settings: SettingsRepository,
    private val history: HistoryRepository,
    private val hostBlocker: HostBlocker,
) : WebViewClient() {

    override fun shouldOverrideUrlLoading(
        view: WebView, request: WebResourceRequest,
    ): Boolean {
        val raw = request.url.toString()
        val cleaned = maybeStripTracking(raw)
        val upgraded = maybeUpgradeHttps(cleaned)
        if (upgraded != raw) {
            view.loadUrl(upgraded)
            return true
        }
        return false
    }

    override fun shouldInterceptRequest(
        view: WebView, request: WebResourceRequest,
    ): WebResourceResponse? {
        if (!settings.load().enableAdblock) return null
        return if (hostBlocker.shouldBlock(request.url.toString())) {
            // 204 No Content keeps the JS that loaded the resource happy
            // while injecting nothing — same trick as a uBlock noop.
            WebResourceResponse(
                "text/plain", "utf-8",
                204, "No Content",
                emptyMap(),
                ByteArrayInputStream(ByteArray(0)),
            )
        } else null
    }

    override fun onPageFinished(view: WebView, url: String) {
        tab.url = url
        tab.title = view.title ?: url
        tab.progress = 100
        history.record(url, tab.title)
        onPageFinishedExtra?.invoke()
    }

    /** Optional UI-thread hook for the page-finished event; set by the screen. */
    var onPageFinishedExtra: (() -> Unit)? = null

    private fun maybeStripTracking(url: String): String =
        if (settings.load().stripTracking) TrackingParams.strip(url) else url

    private fun maybeUpgradeHttps(url: String): String {
        if (!settings.load().httpsOnly) return url
        return if (url.startsWith("http://")) "https://" + url.removePrefix("http://") else url
    }
}
