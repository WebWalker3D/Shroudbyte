"""Encrypted password vault for Blade Browser.

Uses Fernet (AES-128-CBC + HMAC) with a PBKDF2-derived key from a master password.
Vault stored as an encrypted JSON blob at ~/.blade-browser/passwords.enc
Salt stored at ~/.blade-browser/passwords.salt
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

from .storage import DATA_DIR, _ensure_dir

SALT_FILE = "passwords.salt"
VAULT_FILE = "passwords.enc"
VERIFY_FILE = "passwords.verify"
_KDF_ITERATIONS = 100_000


def _derive_key(master_password: str, salt: bytes) -> bytes:
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
        self._fernet: Fernet | None = None
        self._unlocked = False

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
        salt = os.urandom(16)
        (DATA_DIR / SALT_FILE).write_bytes(salt)

        key = _derive_key(master_password, salt)
        f = Fernet(key)

        # Store an encrypted sentinel so we can verify the password later
        (DATA_DIR / VERIFY_FILE).write_bytes(f.encrypt(b"blade-browser-vault"))

        self._fernet = f
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
        key = _derive_key(master_password, salt)
        f = Fernet(key)

        try:
            f.decrypt(verify_path.read_bytes())
        except InvalidToken:
            return False

        self._fernet = f
        self._unlocked = True
        self._load()
        return True

    def lock(self):
        """Lock the vault, clearing decrypted data from memory."""
        self._entries = []
        self._fernet = None
        self._unlocked = False

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

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
        if not self._fernet:
            return
        _ensure_dir()
        data = json.dumps(self._entries).encode("utf-8")
        encrypted = self._fernet.encrypt(data)
        (DATA_DIR / VAULT_FILE).write_bytes(encrypted)

    def _load(self):
        vault_path = DATA_DIR / VAULT_FILE
        if not vault_path.exists() or not self._fernet:
            self._entries = []
            return
        try:
            encrypted = vault_path.read_bytes()
            data = self._fernet.decrypt(encrypted)
            self._entries = json.loads(data.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError):
            self._entries = []
