"""Address book — saved contact profiles for form autofill.

A user has zero or more named "addresses", each containing standard
HTML autocomplete fields (name, organization, street, postal code,
etc.). The injected fill JavaScript uses each input's
``autocomplete=""`` attribute to decide which saved value to write.

Storage transparently encrypts the data file with the password vault's
key when the vault is unlocked, and falls back to plain JSON when no
key is available. The on-disk file is auto-migrated between the two
formats on the first save under a new key state — see
:func:`set_encryption_key`.

File layout (``addresses.dat``):

* Plain JSON: first byte is ``'['`` (a JSON array).
* Encrypted: first byte is :data:`crypto.VAULT_VERSION` (currently 2),
  followed by an AES-256-GCM blob produced by :func:`crypto.encrypt_aead`.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field

from . import crypto, storage


logger = logging.getLogger("shroudbyte.addresses")

# Single file for both formats. The on-disk content distinguishes itself
# by its first byte; see module docstring.
_ADDRESS_FILE = "addresses.dat"

# Legacy plain-JSON file used by the v1 MVP. Auto-migrated on first read.
_LEGACY_ADDRESS_FILE = "addresses.json"


# HTML autocomplete tokens we know how to round-trip. The keys here match
# what ``<input autocomplete="...">`` uses, per the WHATWG spec.
# https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill
AUTOCOMPLETE_FIELDS = (
    "name",            # full name
    "given-name",
    "family-name",
    "organization",
    "street-address",
    "address-line1",
    "address-line2",
    "address-level1",  # state/province
    "address-level2",  # city
    "postal-code",
    "country",
    "country-name",
    "email",
    "tel",
)


# Module-level encryption key. MainWindow flips this when the password
# vault unlocks / locks. None means "no vault available — plain JSON".
_active_key: bytes | None = None


def set_encryption_key(key: bytes | None):
    """Tell the address book whether to encrypt on the next save.

    Passing ``None`` reverts to plain JSON. Passing a 32-byte AES-256 key
    causes the next :func:`_save_all` to produce an encrypted file, and
    subsequent reads to require the same key.

    When a key is being set for the first time *while* an unencrypted
    file already exists on disk, the file is re-encrypted immediately
    so a later vault lock can't leave plaintext PII sitting around.
    """
    global _active_key
    previous = _active_key
    _active_key = key
    if key is not None and previous is None:
        _migrate_plaintext_to_encrypted()


def _migrate_plaintext_to_encrypted():
    """If a plaintext addresses.dat exists, re-write it encrypted.

    Called from :func:`set_encryption_key` on the no-key → key
    transition (i.e. the user just set up the password vault).
    Safe to call when no file exists.
    """
    path = _data_path()
    if not path.exists():
        return
    blob = path.read_bytes()
    if not blob or blob[0] == crypto.VAULT_VERSION:
        return  # Empty or already encrypted.
    try:
        entries = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        # Don't try to migrate a malformed file — _load_all will report it.
        return
    _save_all(entries)
    logger.info("Re-encrypted %d address entries after vault unlock", len(entries))


@dataclass
class Address:
    """A saved address profile."""

    id: str
    label: str  # user-chosen name like "Home" or "Work"
    fields: dict = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


# ---------------------------------------------------------------------------
# On-disk format
# ---------------------------------------------------------------------------

def _data_path():
    return storage.DATA_DIR / _ADDRESS_FILE


def _legacy_path():
    return storage.DATA_DIR / _LEGACY_ADDRESS_FILE


def _load_all() -> list[dict]:
    """Read, decode (decrypt if needed), and return the entry list."""
    path = _data_path()
    legacy = _legacy_path()

    # First-run migration: pick up any plain JSON file written by the
    # MVP version of this module and convert to the new container.
    if not path.exists() and legacy.exists():
        try:
            entries = json.loads(legacy.read_text(encoding="utf-8"))
            _save_all(entries)
            legacy.unlink()
            return entries
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not migrate %s: %s", legacy, e)

    if not path.exists():
        return []

    blob = path.read_bytes()
    if not blob:
        return []

    # First byte tells us the format. Encrypted blobs start with
    # crypto.VAULT_VERSION; plain JSON arrays start with '['.
    if blob[0] == crypto.VAULT_VERSION:
        if _active_key is None:
            # Vault is locked — we can't decrypt. Return empty so the
            # UI gracefully shows "no addresses available" rather than
            # crashing; the on-disk data stays intact.
            logger.info(
                "addresses.dat is encrypted but no key set; "
                "returning empty list"
            )
            return []
        try:
            plaintext = crypto.decrypt_aead(blob, _active_key)
        except Exception as e:
            logger.error(
                "Failed to decrypt addresses.dat (%s); quarantining file",
                e,
                exc_info=True,
            )
            # Don't silently let the next _save_all overwrite a corrupt
            # but possibly recoverable file. Move it aside.
            try:
                path.rename(path.with_name(
                    f"{_ADDRESS_FILE}.corrupted-{int(time.time())}"
                ))
            except OSError:
                pass
            return []
        return json.loads(plaintext.decode("utf-8"))

    # Plain JSON path.
    try:
        return json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.error("addresses.dat is malformed plain JSON: %s", e)
        return []


def _save_all(entries: list[dict]):
    """Write entries back out, encrypting if a key is set."""
    storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _data_path()
    payload = json.dumps(entries, separators=(",", ":")).encode("utf-8")
    if _active_key is not None:
        path.write_bytes(crypto.encrypt_aead(payload, _active_key))
    else:
        path.write_bytes(payload)


# ---------------------------------------------------------------------------
# CRUD API
# ---------------------------------------------------------------------------

def list_addresses() -> list[Address]:
    """Return every saved address, most recently updated first."""
    raw = _load_all()
    addrs = [Address(**r) for r in raw]
    addrs.sort(key=lambda a: a.updated_at, reverse=True)
    return addrs


def get_address(address_id: str) -> Address | None:
    for entry in _load_all():
        if entry.get("id") == address_id:
            return Address(**entry)
    return None


def add_address(label: str, fields: dict) -> Address:
    """Create a new address with the given label and field map."""
    now = time.time()
    addr = Address(
        id=str(uuid.uuid4()),
        label=label or "Untitled",
        fields=_sanitize_fields(fields),
        created_at=now,
        updated_at=now,
    )
    entries = _load_all()
    entries.append(asdict(addr))
    _save_all(entries)
    return addr


def update_address(address_id: str, label: str | None = None,
                   fields: dict | None = None) -> bool:
    """Update label and/or fields on an existing address."""
    entries = _load_all()
    for entry in entries:
        if entry.get("id") != address_id:
            continue
        if label is not None:
            entry["label"] = label or "Untitled"
        if fields is not None:
            entry["fields"] = _sanitize_fields(fields)
        entry["updated_at"] = time.time()
        _save_all(entries)
        return True
    return False


def remove_address(address_id: str) -> bool:
    entries = _load_all()
    new_entries = [e for e in entries if e.get("id") != address_id]
    if len(new_entries) == len(entries):
        return False
    _save_all(new_entries)
    return True


def _sanitize_fields(fields: dict) -> dict:
    """Keep only known autocomplete tokens with string values."""
    return {
        key: str(value).strip()
        for key, value in (fields or {}).items()
        if key in AUTOCOMPLETE_FIELDS and value is not None
        and str(value).strip()
    }
