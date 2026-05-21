package com.shroudbyte.crypto

import org.junit.Assert.*
import org.junit.Test

class CryptoTest {

    private val key: ByteArray = ByteArray(32) { it.toByte() }

    @Test fun `roundtrip recovers plaintext`() {
        val pt = "shroudbyte-test-payload".toByteArray()
        val blob = Crypto.encryptAead(pt, key)
        assertArrayEquals(pt, Crypto.decryptAead(blob, key))
    }

    @Test fun `blob starts with version sentinel`() {
        val blob = Crypto.encryptAead(byteArrayOf(0x00), key)
        assertEquals(Crypto.VAULT_VERSION, blob[0])
    }

    @Test fun `nonce randomises ciphertext`() {
        val pt = "same".toByteArray()
        val a = Crypto.encryptAead(pt, key)
        val b = Crypto.encryptAead(pt, key)
        assertFalse("two encrypts of the same plaintext must differ",
            a.contentEquals(b))
    }

    @Test(expected = Exception::class)
    fun `wrong key throws`() {
        val pt = "x".toByteArray()
        val blob = Crypto.encryptAead(pt, key)
        val wrong = ByteArray(32) { (it + 1).toByte() }
        Crypto.decryptAead(blob, wrong)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `bad key length rejected`() {
        Crypto.encryptAead("x".toByteArray(), ByteArray(16))
    }

    @Test(expected = IllegalArgumentException::class)
    fun `truncated blob rejected`() {
        Crypto.decryptAead(byteArrayOf(Crypto.VAULT_VERSION), key)
    }
}
