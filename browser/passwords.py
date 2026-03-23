"""Encrypted password vault for Shroudbyte.

Uses AES-256-GCM with an Argon2id-derived key from a master password.
Vault stored as an encrypted JSON blob at ~/.shroudbyte/passwords.enc
Salt stored at ~/.shroudbyte/passwords.salt

Legacy vaults (Fernet / PBKDF2) are auto-migrated on first unlock.
"""

import base64
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from . import crypto
from .storage import DATA_DIR, _ensure_dir

SALT_FILE = "passwords.salt"
VAULT_FILE = "passwords.enc"
VERIFY_FILE = "passwords.verify"

# Legacy constant — only used when reading old PBKDF2/Fernet vaults
_KDF_ITERATIONS = 100_000


# ------------------------------------------------------------------
# Key derivation helpers
# ------------------------------------------------------------------

def _derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key using Argon2id (or PBKDF2 fallback)."""
    return crypto.derive_key_argon2id(master_password, salt)


def _derive_key_legacy(master_password: str, salt: bytes) -> bytes:
    """Legacy PBKDF2 derivation that produces a Fernet-compatible key."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))


class PasswordVault:
    """Encrypted credential store secured by a master password."""

    def __init__(self):
        self._entries: list[dict] = []
        self._key: bytes | None = None       # 32-byte AES key (modern)
        self._fernet: Fernet | None = None    # Only set for legacy/keyring paths
        self._unlocked = False
        self._is_modern = False               # True when using AES-256-GCM

    # ------------------------------------------------------------------
    # Master password management
    # ------------------------------------------------------------------

    def is_setup(self) -> bool:
        """True if a master password has been configured."""
        _ensure_dir()
        return (DATA_DIR / SALT_FILE).exists() and (DATA_DIR / VERIFY_FILE).exists()

    def setup(self, master_password: str):
        """Create a new vault with the given master password."""
        _ensure_dir()
        salt = os.urandom(32)
        (DATA_DIR / SALT_FILE).write_bytes(salt)

        key = _derive_key(master_password, salt)

        # Store an encrypted sentinel so we can verify the password later
        (DATA_DIR / VERIFY_FILE).write_bytes(
            crypto.encrypt_aead(b"shroudbyte-vault", key)
        )

        self._key = key
        self._fernet = None
        self._is_modern = True
        self._entries = []
        self._unlocked = True
        self._save()

    def unlock(self, master_password: str) -> bool:
        """Unlock the vault. Returns True on success, False if wrong password."""
        _ensure_dir()
        salt_path = DATA_DIR / SALT_FILE
        verify_path = DATA_DIR / VERIFY_FILE

        if not salt_path.exists() or not verify_path.exists():
            return False

        salt = salt_path.read_bytes()
        verify_blob = verify_path.read_bytes()

        # Detect format: modern blobs start with VAULT_VERSION byte (2)
        if len(verify_blob) > 0 and verify_blob[0] == crypto.VAULT_VERSION:
            return self._unlock_modern(master_password, salt, verify_blob)
        else:
            return self._unlock_legacy(master_password, salt, verify_blob)

    def _unlock_modern(self, master_password: str, salt: bytes,
                       verify_blob: bytes) -> bool:
        """Unlock a modern AES-256-GCM vault."""
        key = _derive_key(master_password, salt)
        try:
            crypto.decrypt_aead(verify_blob, key)
        except Exception:
            return False

        self._key = key
        self._fernet = None
        self._is_modern = True
        self._unlocked = True
        self._load()
        return True

    def _unlock_legacy(self, master_password: str, salt: bytes,
                       verify_blob: bytes) -> bool:
        """Unlock a legacy Fernet vault and auto-migrate to modern crypto."""
        legacy_key = _derive_key_legacy(master_password, salt)
        f = Fernet(legacy_key)

        try:
            f.decrypt(verify_blob)
        except InvalidToken:
            return False

        # Temporarily use Fernet to load existing entries
        self._fernet = f
        self._key = None
        self._is_modern = False
        self._unlocked = True
        self._load()

        # --- Auto-migrate to modern crypto ---
        new_salt = os.urandom(32)
        new_key = _derive_key(master_password, new_salt)

        (DATA_DIR / SALT_FILE).write_bytes(new_salt)
        (DATA_DIR / VERIFY_FILE).write_bytes(
            crypto.encrypt_aead(b"shroudbyte-vault", new_key)
        )

        self._key = new_key
        self._fernet = None
        self._is_modern = True
        self._save()
        return True

    def lock(self):
        """Lock the vault, clearing decrypted data from memory."""
        self._entries = []
        self._key = None
        self._fernet = None
        self._unlocked = False
        self._is_modern = False

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

    # ------------------------------------------------------------------
    # Keyring-backed vault (no master password needed)
    # ------------------------------------------------------------------

    def setup_with_keyring(self):
        """Create a new vault with a random AES-256 key stored in the OS keyring."""
        from . import keyring_backend

        _ensure_dir()
        key = os.urandom(32)
        key_hex = key.hex()
        if not keyring_backend.store_secret("vault_fernet_key", key_hex):
            raise RuntimeError("Failed to store vault key in OS keyring")

        (DATA_DIR / VERIFY_FILE).write_bytes(
            crypto.encrypt_aead(b"shroudbyte-vault", key)
        )

        self._key = key
        self._fernet = None
        self._is_modern = True
        self._entries = []
        self._unlocked = True
        self._save()

    def unlock_with_keyring(self) -> bool:
        """Unlock the vault using the key stored in the OS keyring."""
        from . import keyring_backend

        key_str = keyring_backend.get_secret("vault_fernet_key")
        if not key_str:
            return False

        verify_path = DATA_DIR / VERIFY_FILE
        if not verify_path.exists():
            return False

        verify_blob = verify_path.read_bytes()

        # Detect format: old keyring stores base64 Fernet key (44 chars),
        # new keyring stores hex AES key (64 chars).
        if len(key_str) == 64:
            return self._unlock_keyring_modern(key_str, verify_blob)
        else:
            return self._unlock_keyring_legacy(key_str, verify_blob)

    def _unlock_keyring_modern(self, key_hex: str, verify_blob: bytes) -> bool:
        """Unlock with a modern hex-encoded AES-256 key from the keyring."""
        try:
            key = bytes.fromhex(key_hex)
        except ValueError:
            return False

        try:
            crypto.decrypt_aead(verify_blob, key)
        except Exception:
            return False

        self._key = key
        self._fernet = None
        self._is_modern = True
        self._unlocked = True
        self._load()
        return True

    def _unlock_keyring_legacy(self, key_str: str, verify_blob: bytes) -> bool:
        """Unlock with a legacy Fernet key from the keyring, then auto-migrate."""
        from . import keyring_backend

        try:
            f = Fernet(key_str.encode("ascii"))
            f.decrypt(verify_blob)
        except (InvalidToken, Exception):
            return False

        # Temporarily use Fernet to load existing entries
        self._fernet = f
        self._key = None
        self._is_modern = False
        self._unlocked = True
        self._load()

        # --- Auto-migrate to modern crypto ---
        new_key = os.urandom(32)
        key_hex = new_key.hex()
        if keyring_backend.store_secret("vault_fernet_key", key_hex):
            (DATA_DIR / VERIFY_FILE).write_bytes(
                crypto.encrypt_aead(b"shroudbyte-vault", new_key)
            )
            self._key = new_key
            self._fernet = None
            self._is_modern = True
            self._save()

        return True

    def is_keyring_setup(self) -> bool:
        """True if a vault key exists in the OS keyring and a verify file is present."""
        from . import keyring_backend
        return (
            keyring_backend.get_secret("vault_fernet_key") is not None
            and (DATA_DIR / VERIFY_FILE).exists()
        )

    def migrate_to_keyring(self) -> bool:
        """Migrate an unlocked master-password vault to keyring-backed storage.

        The vault must already be unlocked. Generates a new AES-256 key,
        stores it in the keyring, re-encrypts everything, and removes
        the salt file.
        """
        if not self._unlocked:
            raise RuntimeError("Vault must be unlocked before migration")
        from . import keyring_backend

        key = os.urandom(32)
        key_hex = key.hex()
        if not keyring_backend.store_secret("vault_fernet_key", key_hex):
            return False

        self._key = key
        self._fernet = None
        self._is_modern = True
        (DATA_DIR / VERIFY_FILE).write_bytes(
            crypto.encrypt_aead(b"shroudbyte-vault", key)
        )
        self._save()

        # Salt is no longer needed
        salt_path = DATA_DIR / SALT_FILE
        if salt_path.exists():
            salt_path.unlink()
        return True

    def migrate_to_master_password(self, master_password: str) -> bool:
        """Migrate an unlocked keyring-backed vault to master-password storage.

        Re-encrypts with an Argon2id-derived key and removes the keyring entry.
        """
        if not self._unlocked:
            raise RuntimeError("Vault must be unlocked before migration")
        from . import keyring_backend

        _ensure_dir()
        salt = os.urandom(32)
        (DATA_DIR / SALT_FILE).write_bytes(salt)

        key = _derive_key(master_password, salt)
        self._key = key
        self._fernet = None
        self._is_modern = True
        (DATA_DIR / VERIFY_FILE).write_bytes(
            crypto.encrypt_aead(b"shroudbyte-vault", key)
        )
        self._save()

        keyring_backend.delete_secret("vault_fernet_key")
        return True

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def get_all_entries(self) -> list[dict]:
        return list(self._entries)

    def get_entries_for_url(self, url: str) -> list[dict]:
        """Return entries whose site_url domain matches the given URL's domain."""
        try:
            domain = urlparse(url).hostname or ""
        except Exception:
            return []
        # Match on base domain (strip www.)
        domain = domain.removeprefix("www.")
        results = []
        for entry in self._entries:
            entry_domain = urlparse(entry.get("site_url", "")).hostname or ""
            entry_domain = entry_domain.removeprefix("www.")
            if entry_domain == domain:
                results.append(entry)
        return results

    def add_entry(self, site_url: str, username: str, password: str, name: str = "") -> dict:
        if not self._unlocked:
            raise RuntimeError("Vault is locked")
        entry = {
            "id": str(uuid.uuid4()),
            "site_url": site_url,
            "username": username,
            "password": password,
            "name": name or urlparse(site_url).hostname or site_url,
            "added": time.time(),
            "last_used": 0.0,
        }
        self._entries.append(entry)
        self._save()
        return entry

    def update_entry(self, entry_id: str, **kwargs) -> bool:
        if not self._unlocked:
            raise RuntimeError("Vault is locked")
        for entry in self._entries:
            if entry["id"] == entry_id:
                for k, v in kwargs.items():
                    if k in entry:
                        entry[k] = v
                self._save()
                return True
        return False

    def remove_entry(self, entry_id: str) -> bool:
        if not self._unlocked:
            raise RuntimeError("Vault is locked")
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def touch_entry(self, entry_id: str):
        """Update last_used timestamp."""
        self.update_entry(entry_id, last_used=time.time())

    # ------------------------------------------------------------------
    # Persistence (encrypted)
    # ------------------------------------------------------------------

    def _save(self):
        _ensure_dir()
        data = json.dumps(self._entries).encode("utf-8")
        if self._is_modern and self._key:
            encrypted = crypto.encrypt_aead(data, self._key)
        elif self._fernet:
            encrypted = self._fernet.encrypt(data)
        else:
            return
        (DATA_DIR / VAULT_FILE).write_bytes(encrypted)

    def _load(self):
        vault_path = DATA_DIR / VAULT_FILE
        if not vault_path.exists():
            self._entries = []
            return

        encrypted = vault_path.read_bytes()

        try:
            if self._is_modern and self._key:
                data = crypto.decrypt_aead(encrypted, self._key)
            elif self._fernet:
                data = self._fernet.decrypt(encrypted)
            else:
                self._entries = []
                return
            self._entries = json.loads(data.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError, ValueError, Exception):
            self._entries = []
