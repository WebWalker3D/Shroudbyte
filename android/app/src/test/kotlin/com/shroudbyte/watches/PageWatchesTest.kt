package com.shroudbyte.watches

import com.shroudbyte.storage.Storage
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PageWatchesRepositoryTest {

    @get:Rule val tmp = TemporaryFolder()
    private lateinit var repo: PageWatchesRepository

    @Before fun setup() {
        repo = PageWatchesRepository(Storage(tmp.newFolder("data")))
    }

    @Test fun `empty by default`() {
        assertTrue(repo.all().isEmpty())
    }

    @Test fun `add round-trips through disk`() {
        val w = repo.add("https://example.com", "Example", intervalMinutes = 60)
        val fresh = PageWatchesRepository(Storage(tmp.root.resolve("data")))
        assertEquals(listOf(w.id), fresh.all().map { it.id })
    }

    @Test fun `interval clamps to 5 minimum`() {
        val w = repo.add("https://example.com", "x", intervalMinutes = 1)
        assertEquals(5, w.intervalMinutes)
    }

    @Test fun `adding the same URL refreshes title and stays unique`() {
        val a = repo.add("https://x", "old title")
        val b = repo.add("https://x", "new title")
        assertEquals(a.id, b.id)
        assertEquals(1, repo.all().size)
        assertEquals("new title", repo.all().single().title)
    }

    @Test fun `remove drops by id`() {
        val w = repo.add("https://x", "x")
        assertTrue(repo.remove(w.id))
        assertTrue(repo.all().isEmpty())
        assertFalse(repo.remove("nope"))
    }

    @Test fun `setInterval clamps and persists`() {
        val w = repo.add("https://x", "x")
        repo.setInterval(w.id, 1)
        assertEquals(5, repo.all().single().intervalMinutes)
        repo.setInterval(w.id, 1440)
        assertEquals(1440, repo.all().single().intervalMinutes)
    }

    @Test fun `update writes back fields`() {
        val w = repo.add("https://x", "x")
        repo.update(w.copy(
            lastHash = "deadbeef",
            lastCheckedAt = 1700000000.0,
            lastChangedAt = 1700000100.0,
            lastSnippet = "hi",
        ))
        val refreshed = repo.all().single()
        assertEquals("deadbeef", refreshed.lastHash)
        assertEquals(1700000000.0, refreshed.lastCheckedAt, 0.001)
        assertEquals(1700000100.0, refreshed.lastChangedAt, 0.001)
        assertEquals("hi", refreshed.lastSnippet)
    }
}

class PageWatchOpsTest {

    @Test fun `hash is stable for the same input`() {
        val a = PageWatchOps.hash("hello world".toByteArray())
        val b = PageWatchOps.hash("hello world".toByteArray())
        assertEquals(a, b)
    }

    @Test fun `hash diverges for different input`() {
        val a = PageWatchOps.hash("foo".toByteArray())
        val b = PageWatchOps.hash("bar".toByteArray())
        assertNotEquals(a, b)
    }

    @Test fun `hash is 64 hex chars`() {
        val h = PageWatchOps.hash("anything".toByteArray())
        assertEquals(64, h.length)
        assertTrue(h.all { it in '0'..'9' || it in 'a'..'f' })
    }

    @Test fun `snippet strips tags and collapses whitespace`() {
        val html = """
            <html><head><style>body { color: red; }</style></head>
            <body><h1>Hi</h1><p>Hello   <b>there</b>.</p>
            <script>alert('x')</script></body></html>
        """.trimIndent()
        val text = PageWatchOps.snippet(html)
        assertFalse(text.contains("<"))
        assertFalse(text.contains("alert"))
        assertFalse(text.contains("color: red"))
        assertTrue(text.contains("Hi"))
        assertTrue(text.contains("Hello"))
        assertTrue(text.contains("there"))
    }

    @Test fun `snippet caps length`() {
        val long = "x".repeat(1000)
        assertTrue(PageWatchOps.snippet(long, max = 40).length <= 41) // 40 + ellipsis
    }
}
