"""Encrypted browser state export and import."""

import json
import os
import time

from . import storage
from .crypto import derive_key_argon2id, encrypt_aead, decrypt_aead


# Collections that can be exported
EXPORT_COLLECTIONS = [
    "bookmarks",
    "settings",
    "permissions",
    "cookie_whitelist",
    "site_exceptions",
    "watches",
    "installed_apps",
    "filter_settings",
    "profiles",
    "named_sessions",
]


def export_state(password: str, collections: list[str] | None = None) -> bytes:
    """Export selected browser state as an encrypted blob.

    Returns encrypted bytes that can be written to a file.
    """
    collections = collections or EXPORT_COLLECTIONS

    bundle = {
        "version": 1,
        "exported_at": time.time(),
        "collections": {},
    }

    loaders = {
        "bookmarks": lambda: storage.load_bookmarks(),
        "settings": lambda: storage.load_settings(),
        "permissions": lambda: storage.load_permissions(),
        "cookie_whitelist": lambda: storage.load_cookie_whitelist(),
        "site_exceptions": lambda: storage.load_site_exceptions(),
        "watches": lambda: storage.load_watches(),
        "installed_apps": lambda: storage.load_installed_apps(),
        "filter_settings": lambda: storage._load_json("filter_settings.json", {}),
        "profiles": lambda: storage._load_json("profiles.json", []),
        "named_sessions": lambda: storage._load_json("named_sessions.json", {}),
    }

    for name in collections:
        if name in loaders:
            bundle["collections"][name] = loaders[name]()

    plaintext = json.dumps(bundle, separators=(',', ':')).encode("utf-8")
    salt = os.urandom(32)
    key = derive_key_argon2id(password, salt)
    encrypted = encrypt_aead(plaintext, key)

    # Final format: "SHROUD_EXPORT" magic + salt(32) + encrypted
    return b"SHROUD_EXPORT" + salt + encrypted


def import_state(data: bytes, password: str,
                 collections: list[str] | None = None,
                 merge: bool = True) -> dict:
    """Import browser state from an encrypted export.

    If *merge* is True, data is merged with existing state.
    If False, existing data is overwritten.

    Returns dict of imported collection names and their item counts.
    """
    magic = b"SHROUD_EXPORT"
    if not data.startswith(magic):
        raise ValueError("Not a valid Shroudbyte export file")

    salt = data[len(magic):len(magic) + 32]
    encrypted = data[len(magic) + 32:]

    key = derive_key_argon2id(password, salt)
    plaintext = decrypt_aead(encrypted, key)
    bundle = json.loads(plaintext)

    if bundle.get("version") != 1:
        raise ValueError(f"Unsupported export version: {bundle.get('version')}")

    imported = {}
    collections_data = bundle.get("collections", {})
    allowed = set(collections) if collections else set(EXPORT_COLLECTIONS)

    savers = {
        "bookmarks": storage.save_bookmarks,
        "settings": storage.save_settings,
        "permissions": storage.save_permissions,
        "cookie_whitelist": storage.save_cookie_whitelist,
        "site_exceptions": storage.save_site_exceptions,
        "watches": storage.save_watches,
        "installed_apps": storage.save_installed_apps,
        "filter_settings": lambda d: storage._save_json("filter_settings.json", d),
        "profiles": lambda d: storage._save_json("profiles.json", d),
        "named_sessions": lambda d: storage._save_json("named_sessions.json", d),
    }

    for name, data_val in collections_data.items():
        if name not in allowed or name not in savers:
            continue

        if merge and isinstance(data_val, list):
            # Merge lists by appending new items
            existing = _load_collection(name)
            if isinstance(existing, list):
                existing_urls = {item.get("url") for item in existing if isinstance(item, dict)}
                for item in data_val:
                    if isinstance(item, dict) and item.get("url") not in existing_urls:
                        existing.append(item)
                    elif not isinstance(item, dict):
                        if item not in existing:
                            existing.append(item)
                data_val = existing
        elif merge and isinstance(data_val, dict):
            existing = _load_collection(name)
            if isinstance(existing, dict):
                existing.update(data_val)
                data_val = existing

        savers[name](data_val)
        count = len(data_val) if isinstance(data_val, (list, dict)) else 1
        imported[name] = count

    storage.invalidate_cache()
    return imported


def _load_collection(name: str):
    """Load a collection by name."""
    loaders = {
        "bookmarks": storage.load_bookmarks,
        "settings": storage.load_settings,
        "permissions": storage.load_permissions,
        "cookie_whitelist": storage.load_cookie_whitelist,
        "site_exceptions": storage.load_site_exceptions,
        "watches": storage.load_watches,
        "installed_apps": storage.load_installed_apps,
        "filter_settings": lambda: storage._load_json("filter_settings.json", {}),
        "profiles": lambda: storage._load_json("profiles.json", []),
        "named_sessions": lambda: storage._load_json("named_sessions.json", {}),
    }
    return loaders.get(name, lambda: None)()
