package com.shroudbyte.browser

import com.shroudbyte.storage.Storage
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class SessionRepositoryTest {

    @get:Rule val tmp = TemporaryFolder()
    private lateinit var repo: SessionRepository

    @Before fun setup() {
        repo = SessionRepository(Storage(tmp.newFolder("data")))
    }

    @Test fun `empty load when no file`() {
        assertTrue(repo.load().isEmpty())
    }

    @Test fun `save and load`() {
        val tabs = listOf(
            TabState("https://a.com").also { it.title = "A" },
            TabState("https://b.com").also { it.title = "B" },
        )
        repo.save(tabs)
        val loaded = repo.load()
        assertEquals(listOf("https://a.com", "https://b.com"), loaded.map { it.url })
        assertEquals(listOf("A", "B"), loaded.map { it.title })
    }

    @Test fun `blank and about-blank tabs not persisted`() {
        val tabs = listOf(
            TabState("about:blank").also { it.title = "" },
            TabState("https://real.com").also { it.title = "R" },
            TabState("").also { it.title = "" },
        )
        repo.save(tabs)
        assertEquals(listOf("https://real.com"), repo.load().map { it.url })
    }

    @Test fun `clear empties the file`() {
        repo.save(listOf(TabState("https://x").also { it.title = "x" }))
        repo.clear()
        assertTrue(repo.load().isEmpty())
    }
}
