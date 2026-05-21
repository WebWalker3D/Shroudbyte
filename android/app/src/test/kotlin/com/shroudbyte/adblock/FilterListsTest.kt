package com.shroudbyte.adblock

import com.shroudbyte.storage.Storage
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class FilterListParserTest {

    @Test fun `hosts file parsed`() {
        val text = """
            # Comment
            0.0.0.0 ads.example.com
            0.0.0.0 tracker.example.org
            127.0.0.1 localhost
            127.0.0.1 broadcasthost
            ::1 ip6-localhost
            0.0.0.0 # blank entry
        """.trimIndent()
        val hosts = FilterListParser.parseHosts(text)
        assertTrue("ads.example.com" in hosts)
        assertTrue("tracker.example.org" in hosts)
        // Blocklist sentinels must be skipped.
        assertFalse("localhost" in hosts)
        assertFalse("broadcasthost" in hosts)
    }

    @Test fun `host-only line is accepted`() {
        val text = """
            example.com
            another.example
        """.trimIndent()
        val hosts = FilterListParser.parseHosts(text)
        assertTrue("example.com" in hosts)
        assertTrue("another.example" in hosts)
    }

    @Test fun `pure ip-only lines are rejected`() {
        // We block by host name, never by IP — guards against bizarre lists.
        val text = """
            0.0.0.0 1.2.3.4
            0.0.0.0 192.168.1.1
        """.trimIndent()
        assertTrue(FilterListParser.parseHosts(text).isEmpty())
    }

    @Test fun `abp pure host rules parsed`() {
        val text = """
            ! Comment
            [Adblock Plus 2.0]
            ||ads.example.com^
            ||tracker.example.net^${'$'}third-party
            ||sub.example.org^
        """.trimIndent()
        val hosts = FilterListParser.parseAbp(text)
        assertEquals(
            setOf("ads.example.com", "tracker.example.net", "sub.example.org"),
            hosts,
        )
    }

    @Test fun `abp skips non-host-only rules`() {
        val text = """
            ||example.com/banner.gif
            @@||allowed.com^
            example.com##.ad
            ##.cosmetic-rule
            ! this is a comment
            |https://example.com/foo
        """.trimIndent()
        val hosts = FilterListParser.parseAbp(text)
        assertTrue(hosts.isEmpty())
    }

    @Test fun `abp accepts hosts with subdomain dots`() {
        val text = "||a.b.c.example.com^"
        val hosts = FilterListParser.parseAbp(text)
        assertEquals(setOf("a.b.c.example.com"), hosts)
    }
}

class FilterListPreferencesTest {

    @get:Rule val tmp = TemporaryFolder()

    @Test fun `defaults match source`() {
        val prefs = FilterListPreferences(Storage(tmp.newFolder("data")))
        // EasyList ships disabled in our catalogue; honor that.
        val easylist = FilterLists.SOURCES.first { it.id == "easylist" }
        assertEquals(easylist.defaultEnabled, prefs.isEnabled(easylist))
    }

    @Test fun `explicit toggle persists`() {
        val dir = tmp.newFolder("data")
        val prefs1 = FilterListPreferences(Storage(dir))
        val easylist = FilterLists.SOURCES.first { it.id == "easylist" }
        prefs1.setEnabled(easylist, true)
        val prefs2 = FilterListPreferences(Storage(dir))
        assertTrue(prefs2.isEnabled(easylist))
    }
}
