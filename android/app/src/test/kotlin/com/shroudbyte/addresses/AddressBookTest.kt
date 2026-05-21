package com.shroudbyte.addresses

import com.shroudbyte.crypto.Crypto
import com.shroudbyte.storage.Storage
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class AddressBookTest {

    @get:Rule val tmp = TemporaryFolder()
    private lateinit var dataDir: java.io.File
    private lateinit var book: AddressBook

    private val validFields = mapOf(
        "name" to "Ada Lovelace",
        "street-address" to "1 Foo St",
        "email" to "ada@example.com",
    )

    @Before fun setup() {
        dataDir = tmp.newFolder("data")
        book = AddressBook(Storage(dataDir))
    }

    @Test fun `add round-trips through list`() {
        val a = book.add("Home", validFields)
        val all = book.list()
        assertEquals(1, all.size)
        assertEquals(a.id, all[0].id)
        assertEquals("Ada Lovelace", all[0].fields["name"])
    }

    @Test fun `unknown autocomplete keys dropped`() {
        val a = book.add("Home", validFields + mapOf(
            "credit-card-number" to "BAD",
            "moon_phase" to "waxing",
        ))
        assertFalse("credit-card-number" in a.fields)
        assertFalse("moon_phase" in a.fields)
    }

    @Test fun `empty values dropped`() {
        val a = book.add("Home", mapOf(
            "name" to "Ada",
            "email" to "",
            "tel" to "   ",
        ))
        assertEquals(setOf("name"), a.fields.keys)
    }

    @Test fun `plain JSON when no key`() {
        book.add("Home", validFields)
        val bytes = java.io.File(dataDir, "addresses.dat").readBytes()
        assertEquals('['.code.toByte(), bytes[0])
    }

    @Test fun `encrypted when key set`() {
        val key = Crypto.randomKey()
        book.setEncryptionKey(key)
        val a = book.add("Home", validFields)
        val bytes = java.io.File(dataDir, "addresses.dat").readBytes()
        assertEquals(Crypto.VAULT_VERSION, bytes[0])
        // The plaintext id should NOT appear in the on-disk bytes.
        val asString = bytes.toString(Charsets.UTF_8)
        assertFalse(a.id in asString)
        // Round-trip still resolves.
        assertEquals(a.id, book.get(a.id)?.id)
    }

    @Test fun `locking hides entries`() {
        val key = Crypto.randomKey()
        book.setEncryptionKey(key)
        val a = book.add("Home", validFields)
        book.setEncryptionKey(null)
        assertTrue(book.list().isEmpty())
        book.setEncryptionKey(key)
        assertEquals(a.id, book.list().single().id)
    }

    @Test fun `wrong key quarantines file`() {
        val key = Crypto.randomKey()
        book.setEncryptionKey(key)
        book.add("Home", validFields)
        book.setEncryptionKey(Crypto.randomKey())
        assertTrue(book.list().isEmpty())
        val quarantined = dataDir.listFiles { f -> f.name.startsWith("addresses.dat.corrupted-") }
        assertTrue("expected quarantine sidecar", (quarantined?.size ?: 0) >= 1)
    }

    @Test fun `plaintext file re-encrypts on first key`() {
        book.add("Home", validFields)
        val file = java.io.File(dataDir, "addresses.dat")
        assertEquals('['.code.toByte(), file.readBytes()[0])
        book.setEncryptionKey(Crypto.randomKey())
        assertEquals(Crypto.VAULT_VERSION, file.readBytes()[0])
    }

    @Test fun `remove drops by id`() {
        val a = book.add("Home", validFields)
        assertTrue(book.remove(a.id))
        assertNull(book.get(a.id))
        assertFalse(book.remove("never"))
    }
}
