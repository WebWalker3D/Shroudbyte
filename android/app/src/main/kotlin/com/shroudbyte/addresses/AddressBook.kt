package com.shroudbyte.addresses

import com.shroudbyte.crypto.Crypto
import com.shroudbyte.storage.Storage
import java.util.UUID
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

/**
 * Saved address profiles for form autofill, mirroring `browser/addresses.py`.
 *
 * File format: `addresses.dat`.  First byte distinguishes encrypted
 * (`Crypto.VAULT_VERSION`) from plain JSON (`[`), exactly like the
 * desktop client, so a future cross-device sync can move the file
 * verbatim between platforms.
 */
@Serializable
data class Address(
    val id: String,
    val label: String,
    val fields: Map<String, String> = emptyMap(),
    val createdAt: Double = 0.0,
    val updatedAt: Double = 0.0,
)

class AddressBook(private val storage: Storage) {

    private val json = Json { ignoreUnknownKeys = true }
    private val serializer = ListSerializer(Address.serializer())
    private var activeKey: ByteArray? = null

    /** Tokens the desktop client also round-trips. Unknown tokens are dropped on save. */
    val autocompleteFields = setOf(
        "name", "given-name", "family-name",
        "organization",
        "street-address", "address-line1", "address-line2",
        "address-level1", "address-level2",
        "postal-code",
        "country", "country-name",
        "email", "tel",
    )

    /**
     * Set the AES-256 key used to encrypt the file. Null reverts to
     * plain JSON. The very first time a key is set with an existing
     * plaintext file on disk, the file is re-encrypted immediately —
     * same as the desktop client.
     */
    fun setEncryptionKey(key: ByteArray?) {
        val previous = activeKey
        activeKey = key
        if (key != null && previous == null) {
            migratePlaintextToEncrypted()
        }
    }

    fun list(): List<Address> = loadAll().sortedByDescending { it.updatedAt }

    fun get(id: String): Address? = loadAll().firstOrNull { it.id == id }

    fun add(label: String, fields: Map<String, String>): Address {
        val now = System.currentTimeMillis() / 1000.0
        val addr = Address(
            id = UUID.randomUUID().toString(),
            label = label.ifBlank { "Untitled" },
            fields = sanitize(fields),
            createdAt = now,
            updatedAt = now,
        )
        val current = loadAll().toMutableList()
        current += addr
        saveAll(current)
        return addr
    }

    fun update(id: String, label: String? = null, fields: Map<String, String>? = null): Boolean {
        val current = loadAll().toMutableList()
        val idx = current.indexOfFirst { it.id == id }
        if (idx < 0) return false
        val existing = current[idx]
        current[idx] = existing.copy(
            label = label?.ifBlank { "Untitled" } ?: existing.label,
            fields = fields?.let { sanitize(it) } ?: existing.fields,
            updatedAt = System.currentTimeMillis() / 1000.0,
        )
        saveAll(current)
        return true
    }

    fun remove(id: String): Boolean {
        val current = loadAll()
        val filtered = current.filterNot { it.id == id }
        if (filtered.size == current.size) return false
        saveAll(filtered)
        return true
    }

    // ------------------------------------------------------------------
    // Internal: file format + crypto
    // ------------------------------------------------------------------

    private fun loadAll(): List<Address> {
        val file = storage.raw(FILE)
        if (!file.exists()) return emptyList()
        val bytes = file.readBytes()
        if (bytes.isEmpty()) return emptyList()
        return if (bytes[0] == Crypto.VAULT_VERSION) {
            val key = activeKey ?: return emptyList()  // locked → no addresses
            val plaintext = try {
                Crypto.decryptAead(bytes, key)
            } catch (_: Exception) {
                // Wrong key or corruption: quarantine like the desktop client.
                quarantine(file)
                return emptyList()
            }
            json.decodeFromString(serializer, plaintext.toString(Charsets.UTF_8))
        } else {
            try {
                json.decodeFromString(serializer, bytes.toString(Charsets.UTF_8))
            } catch (_: Exception) {
                emptyList()
            }
        }
    }

    private fun saveAll(entries: List<Address>) {
        val plaintext = json.encodeToString(serializer, entries).toByteArray(Charsets.UTF_8)
        val file = storage.raw(FILE)
        val out = activeKey?.let { Crypto.encryptAead(plaintext, it) } ?: plaintext
        file.writeBytes(out)
    }

    private fun migratePlaintextToEncrypted() {
        val file = storage.raw(FILE)
        if (!file.exists()) return
        val bytes = file.readBytes()
        if (bytes.isEmpty() || bytes[0] == Crypto.VAULT_VERSION) return
        val entries = try {
            json.decodeFromString(serializer, bytes.toString(Charsets.UTF_8))
        } catch (_: Exception) {
            return  // Don't try to migrate a malformed file.
        }
        saveAll(entries)
    }

    private fun quarantine(file: java.io.File) {
        val sidecar = java.io.File(
            file.parent,
            "${file.name}.corrupted-${System.currentTimeMillis() / 1000}"
        )
        file.renameTo(sidecar)
    }

    private fun sanitize(fields: Map<String, String>): Map<String, String> =
        fields.asSequence()
            .filter { (k, v) -> k in autocompleteFields && v.isNotBlank() }
            .associate { (k, v) -> k to v.trim() }

    private companion object {
        const val FILE = "addresses.dat"
    }
}
