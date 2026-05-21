package com.shroudbyte.browser

import android.content.Context
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.widget.Toast

/**
 * WebChromeClient that:
 *   1. Updates per-tab progress + title
 *   2. Denies sensor permission requests by default (privacy posture)
 *
 * A future revision can route these prompts through a Compose dialog
 * with allow/deny + remember controls, mirroring the desktop client's
 * permission ledger.
 */
class ShroudWebChromeClient(
    private val context: Context,
    private val tab: TabState,
) : WebChromeClient() {

    override fun onProgressChanged(view: WebView?, newProgress: Int) {
        tab.progress = newProgress
    }

    override fun onReceivedTitle(view: WebView?, title: String?) {
        if (!title.isNullOrBlank()) tab.title = title
    }

    /** Per-frame device permission requests (mic, camera). Deny by default. */
    override fun onPermissionRequest(request: PermissionRequest) {
        request.deny()
        Toast.makeText(
            context,
            "Permission denied (default): ${request.resources.joinToString()}",
            Toast.LENGTH_SHORT,
        ).show()
    }

    /** Geolocation prompt. Same default-deny posture. */
    override fun onGeolocationPermissionsShowPrompt(
        origin: String?,
        callback: GeolocationPermissions.Callback?,
    ) {
        callback?.invoke(origin ?: "", false, false)
        Toast.makeText(context, "Geolocation denied (default)", Toast.LENGTH_SHORT).show()
    }
}
