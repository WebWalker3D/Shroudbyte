"""Thin abstraction over the system keyring for storing secrets.

Uses the ``keyring`` package which delegates to GNOME Keyring, KDE Wallet,
macOS Keychain, or Windows Credential Locker depending on the platform.
All public functions are safe to call even when no keyring backend is
available — they return ``None`` / ``False`` gracefully.
"""

import logging

logger = logging.getLogger(__name__)

SERVICE_NAME = "Shroudbyte"

try:
    import keyring as _keyring
    import keyring.errors as _keyring_errors
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

_available: bool | None = None  # cached after first probe


def is_available() -> bool:
    """Return True if a functional keyring backend is present.

    Performs a one-time probe (store → read → delete) to ensure the
    backend actually works, not just that the import succeeded.
    """
    global _available
    if _available is not None:
        return _available

    if not _IMPORT_OK:
        _available = False
        return False

    # Reject known-broken or insecure backends
    try:
        backend = _keyring.get_keyring()
        name = type(backend).__module__ + "." + type(backend).__qualname__
        if "fail" in name.lower() or "plaintext" in name.lower():
            logger.info("Keyring backend rejected (insecure): %s", name)
            _available = False
            return False
    except Exception:
        _available = False
        return False

    # Live probe
    probe_key = "_shroudbyte_probe"
    try:
        _keyring.set_password(SERVICE_NAME, probe_key, "ok")
        val = _keyring.get_password(SERVICE_NAME, probe_key)
        _keyring.delete_password(SERVICE_NAME, probe_key)
        _available = val == "ok"
    except Exception:
        logger.debug("Keyring probe failed", exc_info=True)
        _available = False

    if _available:
        logger.info("Keyring available: %s", type(backend).__qualname__)
    else:
        logger.info("Keyring not available")
    return _available


def store_secret(key: str, value: str) -> bool:
    """Store *value* under *key* in the system keyring. Returns False on failure."""
    if not is_available():
        return False
    try:
        _keyring.set_password(SERVICE_NAME, key, value)
        return True
    except Exception:
        logger.warning("Failed to store secret '%s' in keyring", key, exc_info=True)
        return False


def get_secret(key: str) -> str | None:
    """Retrieve a secret from the system keyring. Returns None if not found."""
    if not is_available():
        return None
    try:
        return _keyring.get_password(SERVICE_NAME, key)
    except Exception:
        logger.warning("Failed to read secret '%s' from keyring", key, exc_info=True)
        return None


def delete_secret(key: str) -> bool:
    """Remove a secret from the system keyring. Returns False on failure."""
    if not is_available():
        return False
    try:
        _keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception:
        logger.debug("Failed to delete secret '%s' from keyring", key, exc_info=True)
        return False
