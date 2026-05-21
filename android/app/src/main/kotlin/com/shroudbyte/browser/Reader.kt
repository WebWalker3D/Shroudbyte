package com.shroudbyte.browser

import android.webkit.WebView
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Reader-mode content extractor. Mirrors the JS in
 * `browser/reader.py::READER_EXTRACT_JS` — pulls a clean article
 * payload out of the live DOM so we can render it as a stripped
 * Compose surface instead of the page's chrome / ads / overlays.
 */
@Serializable
data class ReaderArticle(
    val title: String = "",
    val byline: String = "",
    val siteName: String = "",
    val content: String = "",
)

object Reader {

    private val json = Json { ignoreUnknownKeys = true }

    /**
     * Run the extractor in [webView] and call [callback] on the UI
     * thread with the parsed article. The callback receives `null` if
     * the page didn't yield enough content to render in reader view.
     */
    fun extract(webView: WebView, callback: (ReaderArticle?) -> Unit) {
        webView.evaluateJavascript(EXTRACTOR_JS) { raw ->
            val article = try {
                // evaluateJavascript wraps the script's return value in a
                // JSON literal; unwrap.
                if (raw.isNullOrBlank() || raw == "null") null
                else json.decodeFromString(ReaderArticle.serializer(), raw)
            } catch (_: Exception) {
                null
            }
            // Empty payload (nothing extracted) — surface as null.
            callback(article?.takeIf { it.content.isNotBlank() })
        }
    }

    /**
     * Pure JS string, isolated so its only Python-side counterpart is
     * `browser/reader.py::READER_EXTRACT_JS`. Walking through the same
     * heuristics in the same order keeps the two clients' output close
     * enough for cross-platform testing.
     */
    private const val EXTRACTOR_JS = """
        (function() {
            function getMeta(names) {
                for (var i = 0; i < names.length; i++) {
                    var el = document.querySelector(
                        'meta[name="' + names[i] + '"], meta[property="' + names[i] + '"]'
                    );
                    if (el && el.content) return el.content.trim();
                }
                return '';
            }

            var title = '';
            var h1 = document.querySelector('h1');
            if (h1) title = h1.textContent.trim();
            if (!title) title = getMeta(['og:title', 'twitter:title']);
            if (!title) title = document.title || '';

            var byline = getMeta(['author', 'article:author', 'twitter:creator']);
            if (!byline) {
                var byEl = document.querySelector('.byline, .author, [rel="author"], [itemprop="author"]');
                if (byEl) byline = byEl.textContent.trim();
            }

            var siteName = getMeta(['og:site_name']) || location.hostname.replace(/^www\./, '');

            // Candidate-element ranking — semantic tags first, then long
            // text containers, then divs with id/class hinting at content.
            var nodes = [];
            var semantic = document.querySelectorAll('article, main, [role="main"]');
            for (var i = 0; i < semantic.length; i++) nodes.push(semantic[i]);
            var sels = '[id*="content"], [id*="article"], [class*="content"], [class*="article"]';
            var hints = document.querySelectorAll(sels);
            for (var i = 0; i < hints.length; i++) nodes.push(hints[i]);

            function score(n) {
                if (!n) return 0;
                var txt = n.textContent || '';
                if (txt.length < 200) return 0;
                // Penalise nav-y / footer-y blocks.
                var bad = 'nav, footer, header, aside, .sidebar, .comments, .related';
                if (n.matches && n.matches(bad)) return 0;
                return txt.length;
            }
            var best = null, bestScore = 0;
            for (var i = 0; i < nodes.length; i++) {
                var s = score(nodes[i]);
                if (s > bestScore) { bestScore = s; best = nodes[i]; }
            }
            if (!best) {
                // Fall back to the page body when nothing else qualifies.
                best = document.body;
            }

            // Clone so we can scrub without affecting the live page.
            var clone = best.cloneNode(true);
            // Strip noise children.
            var dropSel = 'script, style, noscript, iframe, form, button, input, ' +
                          'nav, footer, aside, .ad, [class*="-ad-"], [aria-hidden="true"]';
            clone.querySelectorAll(dropSel).forEach(function(el) { el.remove(); });

            return JSON.stringify({
                title: title,
                byline: byline,
                siteName: siteName,
                content: clone.innerHTML,
            });
        })();
    """
}
