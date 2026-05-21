package com.shroudbyte.browser

import android.webkit.WebView
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.UUID

/**
 * One open browser tab. Compose observes the mutableState wrappers so
 * the UI reflects URL / title / progress without manual signal wiring.
 */
class TabState(initialUrl: String = "about:blank") {
    val id: String = UUID.randomUUID().toString()
    var url: String by mutableStateOf(initialUrl)
    var title: String by mutableStateOf("New tab")
    var progress: Int by mutableStateOf(0)
    var canGoBack: Boolean by mutableStateOf(false)
    var canGoForward: Boolean by mutableStateOf(false)
    /** Last time the user activated this tab; used by the hibernation pass. */
    var lastActive: Long by mutableStateOf(System.currentTimeMillis())

    /** Reference to the WebView so toolbar actions can drive it. Cleared on tab close. */
    var webView: WebView? = null
}
