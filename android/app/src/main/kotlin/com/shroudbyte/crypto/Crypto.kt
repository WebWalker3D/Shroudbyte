package com.shroudbyte.crypto

import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Cryptographic primitives mirroring `browser/crypto.py`.
 *
 * On-disk format for [encryptAead] / [decryptAead] is byte-compatible with
 * the desktop client so a future export/import path can move data between
 * platforms: `version (1) || nonce (12) || ciphertext+tag`.
 */
object Crypto {

    /** Sentinel byte at the start of every encrypted blob. Bump on format change. */
    const val VAULT_VERSION: Byte = 2

    private const val GCM_TAG_BITS = 128
    private const val NONCE_LEN = 12
    private val rng = SecureRandom()

    /** Encrypt [plaintext] with [key] (32 bytes for AES-256). */
    fun encryptAead(plaintext: ByteArray, key: ByteArray): ByteArray {
        require(key.size == 32) { "AES-256 key must be 32 bytes (got ${key.size})" }
        val nonce = ByteArray(NONCE_LEN).also(rng::nextBytes)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"),
                    GCMParameterSpec(GCM_TAG_BITS, nonce))
        val ct = cipher.doFinal(plaintext)
        val out = ByteArray(1 + NONCE_LEN + ct.size)
        out[0] = VAULT_VERSION
        System.arraycopy(nonce, 0, out, 1, NONCE_LEN)
        System.arraycopy(ct, 0, out, 1 + NONCE_LEN, ct.size)
        return out
    }

    /** Decrypt a blob produced by [encryptAead]. Throws on tamper / wrong key. */
    fun decryptAead(blob: ByteArray, key: ByteArray): ByteArray {
        require(key.size == 32) { "AES-256 key must be 32 bytes (got ${key.size})" }
        require(blob.size >= 1 + NONCE_LEN + 16) { "Blob too short to be a valid AEAD frame" }
        require(blob[0] == VAULT_VERSION) {
            "Unknown vault version: ${blob[0].toInt() and 0xFF}"
        }
        val nonce = blob.copyOfRange(1, 1 + NONCE_LEN)
        val ct = blob.copyOfRange(1 + NONCE_LEN, blob.size)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"),
                    GCMParameterSpec(GCM_TAG_BITS, nonce))
        return cipher.doFinal(ct)
    }

    /** Generate a fresh 32-byte AES-256 key. */
    fun randomKey(): ByteArray = ByteArray(32).also(rng::nextBytes)
}
