"""Tests for browser.crypto — modern cryptographic primitives."""

import os
import pytest

from browser.crypto import (
    VAULT_VERSION,
    derive_key_argon2id,
    encrypt_aead,
    decrypt_aead,
)


class TestEncryptDecryptRoundTrip:

    def test_basic_round_trip(self):
        key = os.urandom(32)
        plaintext = b"hello, world"
        blob = encrypt_aead(plaintext, key)
        assert decrypt_aead(blob, key) == plaintext

    def test_empty_plaintext(self):
        key = os.urandom(32)
        blob = encrypt_aead(b"", key)
        assert decrypt_aead(blob, key) == b""

    def test_large_plaintext(self):
        key = os.urandom(32)
        plaintext = os.urandom(1_000_000)
        blob = encrypt_aead(plaintext, key)
        assert decrypt_aead(blob, key) == plaintext


class TestWrongKeyRaises:

    def test_wrong_key_raises(self):
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        blob = encrypt_aead(b"secret data", key1)
        with pytest.raises(Exception):
            decrypt_aead(blob, key2)


class TestVersionByte:

    def test_version_byte_is_correct(self):
        key = os.urandom(32)
        blob = encrypt_aead(b"test", key)
        assert blob[0] == VAULT_VERSION

    def test_wrong_version_raises(self):
        key = os.urandom(32)
        blob = encrypt_aead(b"test", key)
        # Corrupt the version byte
        bad_blob = bytes([VAULT_VERSION + 1]) + blob[1:]
        with pytest.raises(ValueError, match="Unknown vault version"):
            decrypt_aead(bad_blob, key)


class TestDeriveKeyArgon2id:

    def test_deterministic(self):
        salt = os.urandom(32)
        k1 = derive_key_argon2id("password", salt)
        k2 = derive_key_argon2id("password", salt)
        assert k1 == k2

    def test_key_length(self):
        salt = os.urandom(32)
        key = derive_key_argon2id("password", salt)
        assert len(key) == 32

    def test_different_password_different_key(self):
        salt = os.urandom(32)
        k1 = derive_key_argon2id("password1", salt)
        k2 = derive_key_argon2id("password2", salt)
        assert k1 != k2

    def test_different_salt_different_key(self):
        s1 = os.urandom(32)
        s2 = os.urandom(32)
        k1 = derive_key_argon2id("password", s1)
        k2 = derive_key_argon2id("password", s2)
        assert k1 != k2


class TestBlobFormat:

    def test_blob_structure(self):
        """Blob = version(1) || nonce(12) || ciphertext+tag."""
        key = os.urandom(32)
        plaintext = b"hello"
        blob = encrypt_aead(plaintext, key)
        # Version byte
        assert blob[0] == VAULT_VERSION
        # Nonce is 12 bytes
        nonce = blob[1:13]
        assert len(nonce) == 12
        # Remaining is ciphertext (len(plaintext)) + GCM tag (16 bytes)
        ct_and_tag = blob[13:]
        assert len(ct_and_tag) == len(plaintext) + 16

    def test_blob_too_short_raises(self):
        key = os.urandom(32)
        with pytest.raises(ValueError, match="Blob too short"):
            decrypt_aead(b"\x02short", key)

    def test_different_nonces_per_encrypt(self):
        """Each encryption should produce a different nonce."""
        key = os.urandom(32)
        blob1 = encrypt_aead(b"same", key)
        blob2 = encrypt_aead(b"same", key)
        nonce1 = blob1[1:13]
        nonce2 = blob2[1:13]
        assert nonce1 != nonce2
