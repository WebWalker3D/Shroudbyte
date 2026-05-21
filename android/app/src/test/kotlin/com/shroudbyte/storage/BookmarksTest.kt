package com.shroudbyte.storage

import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class BookmarksTest {

    @get:Rule val tmp = TemporaryFolder()
    private lateinit var repo: BookmarksRepository

    @Before fun setup() {
        repo = BookmarksRepository(Storage(tmp.newFolder("data")))
    }

    @Test fun `add and load`() {
        assertTrue(repo.add("Example", "https://example.com"))
        val all = repo.all()
        assertEquals(1, all.size)
        assertEquals("https://example.com", all[0].url)
    }

    @Test fun `duplicate URL rejected`() {
        repo.add("First", "https://example.com")
        assertFalse(repo.add("Second", "https://example.com"))
        assertEquals(1, repo.all().size)
    }

    @Test fun `blank title falls back to url`() {
        repo.add("", "https://example.com")
        assertEquals("https://example.com", repo.all()[0].title)
    }

    @Test fun `remove drops by url`() {
        repo.add("a", "https://a.com")
        repo.add("b", "https://b.com")
        repo.remove("https://a.com")
        assertEquals(listOf("https://b.com"), repo.all().map { it.url })
    }

    @Test fun `reorder respects given order`() {
        repo.add("a", "https://a.com")
        repo.add("b", "https://b.com")
        repo.add("c", "https://c.com")
        repo.reorder(listOf("https://c.com", "https://a.com", "https://b.com"))
        assertEquals(
            listOf("https://c.com", "https://a.com", "https://b.com"),
            repo.all().map { it.url },
        )
    }

    @Test fun `reorder ignores unknown urls`() {
        repo.add("a", "https://a.com")
        repo.reorder(listOf("https://ghost", "https://a.com"))
        assertEquals(listOf("https://a.com"), repo.all().map { it.url })
    }
}
