package com.shroudbyte.passwords

import com.shroudbyte.crypto.Crypto
import com.shroudbyte.storage.Storage
import java.io.File
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.UUID
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

/**
 * Encrypted credential vault mirroring `browser/passwords.py`.
 *
 * On-disk layout:
 *   passwords.salt   — 32 random bytes seeded once at setup
 *   passwords.verify — encryption of the literal string "shroudbyte-vault"
 *                      with the derived key, used to check unlock passwords
 *   passwords.enc    — the encrypted JSON entry list
 *
 * The verify file lets us tell "wrong password" from "decryption of a
 * corrupt vault failed" — same trick the desktop client uses to know
 * when to quarantine.
 */
@Serializable
data class PasswordEntry(
    val id: String,
    val siteUrl: String,
    val username: String,
    val password: String,
    val name: String = "",
    val added: Double = 0.0,
    val lastUsed: Double = 0.0,
)

class PasswordVault(private val storage: Storage) {

    private val json = Json { ignoreUnknownKeys = true }
    private val serializer = ListSerializer(PasswordEntry.serializer())
    private val rng = SecureRandom()

    private var key: ByteArray? = null
    private var entries: List<PasswordEntry> = emptyList()

    val isUnlocked: Boolean get() = key != null
    fun isSetUp(): Boolean = saltFile().exists() && verifyFile().exists()

    private val verifyPlaintext = "shroudbyte-vault".toByteArray(Charsets.UTF_8)

    // ------------------------------------------------------------------
    // Setup / unlock / lock
    // ------------------------------------------------------------------

    /** Create a brand-new vault. Fails fast if one already exists. */
    fun setup(masterPassword: String) {
        check(!isSetUp()) { "Vault is already set up" }
        val salt = ByteArray(32).also(rng::nextBytes)
        val derived = deriveKey(masterPassword, salt)
        val verifyBlob = Crypto.encryptAead(verifyPlaintext, derived)
        saltFile().writeBytes(salt)
        verifyFile().writeBytes(verifyBlob)
        key = derived
        entries = emptyList()
        save()
    }

    /**
     * Unlock an existing vault. Returns false for a wrong password.
     * For an actually-corrupt verify file we still return false here
     * (no way to know which), but [load] separately handles a corrupt
     * entries file by quarantining.
     */
    fun unlock(masterPassword: String): Boolean {
        if (!isSetUp()) return false
        val salt = saltFile().readBytes()
        val verifyBlob = verifyFile().readBytes()
        val derived = deriveKey(masterPassword, salt)
        val ok = try {
            Crypto.decryptAead(verifyBlob, derived).contentEquals(verifyPlaintext)
        } catch (_: Exception) {
            false
        }
        if (!ok) return false
        key = derived
        load()
        return true
    }

    fun lock() {
        key = null
        entries = emptyList()
    }

    // ------------------------------------------------------------------
    // CRUD
    // ------------------------------------------------------------------

    fun all(): List<PasswordEntry> = entries.toList()

    fun forUrl(url: String): List<PasswordEntry> {
        val host = extractHost(url) ?: return emptyList()
        return entries.filter { extractHost(it.siteUrl) == host }
    }

    fun add(siteUrl: String, username: String, password: String, name: String = ""): PasswordEntry {
        check(isUnlocked) { "Vault is locked" }
        val now = System.currentTimeMillis() / 1000.0
        val entry = PasswordEntry(
            id = UUID.randomUUID().toString(),
            siteUrl = siteUrl,
            username = username,
            password = password,
            name = name.ifBlank { extractHost(siteUrl) ?: siteUrl },
            added = now,
            lastUsed = 0.0,
        )
        entries = entries + entry
        save()
        return entry
    }

    fun update(id: String, username: String? = null, password: String? = null,
               name: String? = null): Boolean {
        check(isUnlocked) { "Vault is locked" }
        val idx = entries.indexOfFirst { it.id == id }
        if (idx < 0) return false
        val cur = entries[idx]
        entries = entries.toMutableList().apply {
            this[idx] = cur.copy(
                username = username ?: cur.username,
                password = password ?: cur.password,
                name = name ?: cur.name,
            )
        }
        save()
        return true
    }

    fun remove(id: String): Boolean {
        check(isUnlocked) { "Vault is locked" }
        val next = entries.filterNot { it.id == id }
        if (next.size == entries.size) return false
        entries = next
        save()
        return true
    }

    fun touch(id: String) {
        if (!isUnlocked) return
        val idx = entries.indexOfFirst { it.id == id }
        if (idx >= 0) {
            entries = entries.toMutableList().apply {
                this[idx] = this[idx].copy(lastUsed = System.currentTimeMillis() / 1000.0)
            }
            save()
        }
    }

    // ------------------------------------------------------------------
    // Persistence
    // ------------------------------------------------------------------

    private fun save() {
        val k = key ?: return
        val plaintext = json.encodeToString(serializer, entries).toByteArray(Charsets.UTF_8)
        vaultFile().writeBytes(Crypto.encryptAead(plaintext, k))
    }

    private fun load() {
        val k = key ?: return
        val file = vaultFile()
        if (!file.exists()) {
            entries = emptyList()
            return
        }
        val blob = file.readBytes()
        if (blob.isEmpty()) {
            entries = emptyList()
            return
        }
        entries = try {
            val plaintext = Crypto.decryptAead(blob, k)
            json.decodeFromString(serializer, plaintext.toString(Charsets.UTF_8))
        } catch (_: Exception) {
            // Quarantine the corrupt file so the next _save() can't
            // overwrite it. Same pattern as the addresses module.
            quarantine(file)
            emptyList()
        }
    }

    private fun quarantine(file: File) {
        val sidecar = File(
            file.parent,
            "${file.name}.corrupted-${System.currentTimeMillis() / 1000}",
        )
        file.renameTo(sidecar)
    }

    // ------------------------------------------------------------------
    // Key derivation
    //
    // The desktop client prefers Argon2id, falling back to PBKDF2 when
    // argon2-cffi is missing. Android's javax.crypto only ships PBKDF2;
    // we use PBKDF2-HMAC-SHA256 at 600k iterations, identical to the
    // desktop fallback path so a future cross-platform import works.
    // ------------------------------------------------------------------

    private fun deriveKey(password: String, salt: ByteArray): ByteArray {
        val spec = PBEKeySpec(password.toCharArray(), salt, 600_000, 256)
        val factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
        return factory.generateSecret(spec).encoded
    }

    // ------------------------------------------------------------------
    // Path helpers
    // ------------------------------------------------------------------

    private fun saltFile() = storage.raw("passwords.salt")
    private fun verifyFile() = storage.raw("passwords.verify")
    private fun vaultFile() = storage.raw("passwords.enc")

    /** Best-effort hostname extraction without depending on android.net.Uri. */
    private fun extractHost(url: String): String? {
        val withoutScheme = url.substringAfter("://", url)
        val noPath = withoutScheme.substringBefore('/')
        val noPort = noPath.substringBefore(':')
        return noPort.removePrefix("www.").ifBlank { null }?.lowercase()
    }
}
