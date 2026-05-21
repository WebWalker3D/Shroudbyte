package com.shroudbyte.browser

import org.junit.Assert.*
import org.junit.Test

class ReaderTest {

    // The extractor JS is accessed reflectively because it's `private const`
    // — we'd rather not weaken its visibility just for tests, and a string
    // shape check is enough to catch obvious breaks.
    private val js: String by lazy {
        Reader::class.java.getDeclaredField("EXTRACTOR_JS")
            .apply { isAccessible = true }
            .get(null) as String
    }

    @Test fun `is iife`() {
        val trimmed = js.trim()
        assertTrue(trimmed.startsWith("(function()") || trimmed.startsWith("(function ()"))
        assertTrue(trimmed.endsWith("})();"))
    }

    @Test fun `covers metadata sources`() {
        for (needle in listOf("og:title", "twitter:title", "document.title",
                              "article:author", "og:site_name")) {
            assertTrue("missing metadata source: $needle", js.contains(needle))
        }
    }

    @Test fun `drops noisy children before returning`() {
        // The clone-and-strip pass must remove scripts and friends so the
        // article HTML we return is safe to render under javaScriptEnabled=false.
        for (needle in listOf("script", "iframe", "form", "button", "nav, footer, aside")) {
            assertTrue("missing scrubber for: $needle", js.contains(needle))
        }
    }

    @Test fun `returns a JSON payload`() {
        assertTrue(js.contains("JSON.stringify"))
    }
}
