package com.shroudbyte.passwords

import com.shroudbyte.storage.Storage
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PasswordVaultTest {

    @get:Rule val tmp = TemporaryFolder()
    private lateinit var dataDir: java.io.File
    private lateinit var vault: PasswordVault

    private val master = "correct-horse-battery-staple"

    @Before fun setup() {
        dataDir = tmp.newFolder("data")
        vault = PasswordVault(Storage(dataDir))
    }

    @Test fun `not set up on fresh data dir`() {
        assertFalse(vault.isSetUp())
        assertFalse(vault.isUnlocked)
    }

    @Test fun `setup leaves vault unlocked`() {
        vault.setup(master)
        assertTrue(vault.isSetUp())
        assertTrue(vault.isUnlocked)
    }

    @Test(expected = IllegalStateException::class)
    fun `setup twice fails`() {
        vault.setup(master)
        vault.setup("other")
    }

    @Test fun `unlock with correct password succeeds`() {
        vault.setup(master)
        vault.lock()
        assertTrue(vault.unlock(master))
        assertTrue(vault.isUnlocked)
    }

    @Test fun `unlock with wrong password fails`() {
        vault.setup(master)
        vault.lock()
        assertFalse(vault.unlock("wrong"))
        assertFalse(vault.isUnlocked)
    }

    @Test fun `add entry round-trips`() {
        vault.setup(master)
        val e = vault.add("https://example.com", "ada", "secret", name = "Example")
        val all = vault.all()
        assertEquals(1, all.size)
        assertEquals("ada", all[0].username)
        assertEquals("secret", all[0].password)
        assertEquals(e.id, all[0].id)
    }

    @Test fun `entries survive lock and unlock`() {
        vault.setup(master)
        vault.add("https://example.com", "ada", "secret")
        vault.lock()
        val fresh = PasswordVault(Storage(dataDir))
        assertTrue(fresh.unlock(master))
        assertEquals(listOf("ada"), fresh.all().map { it.username })
    }

    @Test fun `forUrl matches host ignoring www and path`() {
        vault.setup(master)
        vault.add("https://www.example.com/login", "ada", "p")
        val hits = vault.forUrl("https://example.com/account")
        assertEquals(1, hits.size)
        assertEquals("ada", hits[0].username)
    }

    @Test fun `forUrl filters by host`() {
        vault.setup(master)
        vault.add("https://a.com", "ada", "x")
        vault.add("https://b.com", "bob", "y")
        assertEquals(listOf("ada"), vault.forUrl("https://a.com").map { it.username })
        assertEquals(listOf("bob"), vault.forUrl("https://b.com").map { it.username })
    }

    @Test fun `update changes the entry in place`() {
        vault.setup(master)
        val e = vault.add("https://a.com", "ada", "old")
        assertTrue(vault.update(e.id, password = "new", name = "Renamed"))
        val refreshed = vault.all().single()
        assertEquals("new", refreshed.password)
        assertEquals("Renamed", refreshed.name)
        // Username preserved.
        assertEquals("ada", refreshed.username)
    }

    @Test fun `remove drops by id`() {
        vault.setup(master)
        val e = vault.add("https://a.com", "ada", "x")
        assertTrue(vault.remove(e.id))
        assertTrue(vault.all().isEmpty())
        assertFalse(vault.remove(e.id))
    }

    @Test(expected = IllegalStateException::class)
    fun `add when locked fails`() {
        vault.setup(master)
        vault.lock()
        vault.add("https://a.com", "ada", "x")
    }

    @Test fun `corrupt vault file is quarantined`() {
        vault.setup(master)
        vault.add("https://a.com", "ada", "x")
        vault.lock()
        // Smash the encrypted file.
        java.io.File(dataDir, "passwords.enc").writeBytes(byteArrayOf(0x02, 0, 0, 0))
        val fresh = PasswordVault(Storage(dataDir))
        // Unlock still succeeds (verify file is fine); but the entries
        // file decrypts to nothing and is renamed aside.
        assertTrue(fresh.unlock(master))
        assertTrue(fresh.all().isEmpty())
        val q = dataDir.listFiles { f -> f.name.startsWith("passwords.enc.corrupted-") }
        assertTrue("expected quarantine sidecar", (q?.size ?: 0) >= 1)
    }
}
