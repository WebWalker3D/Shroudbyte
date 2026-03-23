"""Modern cryptographic primitives for Shroudbyte."""

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Vault format version — embedded as first byte of encrypted blobs
VAULT_VERSION = 2

def derive_key_argon2id(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte key using Argon2id."""
    try:
        from argon2.low_level import hash_secret_raw, Type
        return hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=3,
            memory_cost=65536,  # 64 MiB
            parallelism=4,
            hash_len=32,
            type=Type.ID,
        )
    except ImportError:
        # Fallback to PBKDF2 if argon2-cffi not installed
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        return kdf.derive(password.encode("utf-8"))

def encrypt_aead(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with AES-256-GCM. Returns: version(1) || nonce(12) || ciphertext+tag."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return bytes([VAULT_VERSION]) + nonce + ct

def decrypt_aead(blob: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM blob. Raises on wrong key or corruption."""
    if len(blob) < 14:
        raise ValueError("Blob too short")
    version = blob[0]
    if version != VAULT_VERSION:
        raise ValueError(f"Unknown vault version: {version}")
    nonce = blob[1:13]
    ct = blob[13:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)
