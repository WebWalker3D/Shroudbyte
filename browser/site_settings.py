"""Per-site settings — override global defaults for individual hosts."""

from .db import get_db

# Setting keys and their types/defaults
SITE_SETTING_KEYS = {
    "js_enabled": True,
    "cookies_enabled": True,
    "images_enabled": True,
    "media_autoplay": False,
    "fingerprint_resistance": False,
    "referrer_policy": "default",  # "default", "no-referrer", "origin"
    "webrtc_policy": "default",  # "default", "disable_non_proxied_udp"
}


def get_site_settings(host: str) -> dict:
    """Return merged settings for a host (global defaults + per-site overrides)."""
    db = get_db()
    overrides = db.get_site_settings(host)
    result = dict(SITE_SETTING_KEYS)
    result.update(overrides)
    return result


def set_site_setting(host: str, key: str, value):
    """Set a single per-site setting."""
    if key not in SITE_SETTING_KEYS:
        return
    db = get_db()
    db.set_site_setting(host, key, value)


def remove_site_settings(host: str):
    """Remove all per-site overrides for a host."""
    db = get_db()
    db.remove_site_settings(host)


def get_all_customized_hosts() -> list[str]:
    """Return hosts that have per-site overrides."""
    db = get_db()
    return db.get_customized_hosts()
