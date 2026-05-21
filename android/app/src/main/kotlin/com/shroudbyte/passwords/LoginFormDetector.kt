package com.shroudbyte.passwords

import android.webkit.WebView

/**
 * Tiny JS probe that reports whether the page has a visible password
 * field. We use the result to decide whether to surface a "Fill
 * credentials" banner, so the user only sees the banner on actual
 * login pages.
 */
object LoginFormDetector {

    /** Probe [webView]; [callback] receives `true` if a login form looks present. */
    fun probe(webView: WebView, callback: (Boolean) -> Unit) {
        webView.evaluateJavascript(PROBE_JS) { raw ->
            callback(raw?.trim() == "true")
        }
    }

    private const val PROBE_JS = """
        (function() {
            var inputs = document.querySelectorAll('input[type="password"]');
            for (var i = 0; i < inputs.length; i++) {
                var el = inputs[i];
                if (el.disabled) continue;
                var s = window.getComputedStyle(el);
                if (s.display === 'none' || s.visibility === 'hidden') continue;
                if (el.offsetWidth <= 0 || el.offsetHeight <= 0) continue;
                return true;
            }
            return false;
        })();
    """
}
