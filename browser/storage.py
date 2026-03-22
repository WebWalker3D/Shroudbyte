"""Persistent storage for bookmarks, history, settings, and blocked hosts."""

import json
import os
import time
from pathlib import Path


DATA_DIR = Path(os.environ.get("SHROUDBYTE_DATA_DIR", Path.home() / ".shroudbyte"))


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Generic JSON helpers
# ---------------------------------------------------------------------------

def _load_json(filename, default=None):
    _ensure_dir()
    path = DATA_DIR / filename
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default if default is not None else []


def _save_json(filename, data):
    _ensure_dir()
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------

def load_bookmarks():
    return _load_json("bookmarks.json", [])


def save_bookmarks(bookmarks):
    _save_json("bookmarks.json", bookmarks)


def add_bookmark(title, url):
    bm = load_bookmarks()
    if any(b["url"] == url for b in bm):
        return False
    bm.append({"title": title, "url": url, "added": time.time()})
    save_bookmarks(bm)
    return True


def remove_bookmark(url):
    bm = load_bookmarks()
    bm = [b for b in bm if b["url"] != url]
    save_bookmarks(bm)


def is_bookmarked(url):
    return any(b["url"] == url for b in load_bookmarks())


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def load_history():
    return _load_json("history.json", [])


def save_history(history):
    _save_json("history.json", history)


def add_history_entry(title, url):
    hist = load_history()
    hist.insert(0, {"title": title, "url": url, "visited": time.time()})
    # Keep the last 5000 entries
    if len(hist) > 5000:
        hist = hist[:5000]
    save_history(hist)


def clear_history():
    save_history([])


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "search_engine": "https://duckduckgo.com/?q={}",
    "enable_javascript": True,
    "enable_adblock": True,
    "private_mode": False,
    "default_zoom": 100,
    "user_agent": "",
    "https_only": False,
    "do_not_track": True,
    "restore_session": True,
    "strip_tracking": True,
    "fingerprint_resistance": False,
    "dns_over_https": "automatic",
    "dns_over_https_provider": "https://dns.cloudflare.com/dns-query",
    "custom_dns_enabled": False,
    "custom_dns_server": "",
    "custom_dns_secret": "",
    "custom_dns_fallback": True,
    "custom_dns_cert_fingerprint": "",
    "filterlist_last_update": 0,
    "vault_backend": "master_password",
    "auto_delete_cookies": False,
}


def load_settings():
    settings = _load_json("settings.json", {})
    merged = {**DEFAULT_SETTINGS, **settings}
    return merged


def save_settings(settings):
    _save_json("settings.json", settings)


# ---------------------------------------------------------------------------
# DNS secret helpers (keyring-aware)
# ---------------------------------------------------------------------------

def get_dns_secret(settings: dict) -> str:
    """Return the DNS HMAC secret from the keyring.

    Falls back to settings.json only to support one-time migration of
    secrets that were stored before keyring support was added.
    """
    from . import keyring_backend
    val = keyring_backend.get_secret("dns_secret")
    if val is not None:
        return val
    # Legacy fallback — migrate on next save
    return settings.get("custom_dns_secret", "")


def get_dns_cert_fingerprint(settings: dict) -> str:
    """Return the DNS cert fingerprint from the keyring."""
    from . import keyring_backend
    val = keyring_backend.get_secret("dns_cert_fingerprint")
    if val is not None:
        return val
    return settings.get("custom_dns_cert_fingerprint", "")


def save_dns_secrets(settings: dict, secret: str, fingerprint: str):
    """Store DNS secrets in the OS keyring.

    Raises RuntimeError if the keyring is not available — secrets must
    never be written to settings.json in plaintext.
    """
    from . import keyring_backend
    if not keyring_backend.is_available():
        raise RuntimeError(
            "OS keyring is not available. Cannot store DNS credentials securely.\n"
            "Install and configure a system keyring (GNOME Keyring, KDE Wallet, etc.)."
        )
    if not keyring_backend.store_secret("dns_secret", secret):
        raise RuntimeError("Failed to store DNS secret in OS keyring.")
    if fingerprint:
        keyring_backend.store_secret("dns_cert_fingerprint", fingerprint)
    # Ensure plaintext is never in settings.json
    settings["custom_dns_secret"] = ""
    settings["custom_dns_cert_fingerprint"] = ""


def clear_dns_secrets(settings: dict):
    """Remove DNS secrets from both keyring and settings dict."""
    from . import keyring_backend
    keyring_backend.delete_secret("dns_secret")
    keyring_backend.delete_secret("dns_cert_fingerprint")
    settings["custom_dns_secret"] = ""
    settings["custom_dns_cert_fingerprint"] = ""


# ---------------------------------------------------------------------------
# Ad-block host list
# ---------------------------------------------------------------------------

def load_blocked_hosts():
    path = DATA_DIR / "blocked_hosts.txt"
    if path.exists():
        with open(path, "r") as f:
            return set(line.strip() for line in f if line.strip() and not line.startswith("#"))
    return set()


def save_blocked_hosts(hosts):
    _ensure_dir()
    path = DATA_DIR / "blocked_hosts.txt"
    with open(path, "w") as f:
        f.write("# Shroudbyte blocked hosts list\n")
        for h in sorted(hosts):
            f.write(h + "\n")


# ---------------------------------------------------------------------------
# Session restore
# ---------------------------------------------------------------------------

def save_session(tabs):
    """Save list of tab dicts [{url, title}, ...] for session restore."""
    _save_json("session.json", tabs)


def load_session():
    """Load saved session tabs. Returns list of {url, title} dicts."""
    return _load_json("session.json", [])


def clear_session():
    path = DATA_DIR / "session.json"
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Cookie auto-delete whitelist
# ---------------------------------------------------------------------------

def load_cookie_whitelist() -> list[str]:
    return _load_json("cookie_whitelist.json", [])


def save_cookie_whitelist(whitelist: list[str]):
    _save_json("cookie_whitelist.json", whitelist)


def add_cookie_whitelist(domain: str):
    domain = domain.lstrip(".")
    wl = load_cookie_whitelist()
    if domain not in wl:
        wl.append(domain)
        save_cookie_whitelist(wl)


def remove_cookie_whitelist(domain: str):
    domain = domain.lstrip(".")
    wl = load_cookie_whitelist()
    wl = [d for d in wl if d != domain]
    save_cookie_whitelist(wl)


def is_cookie_whitelisted(domain: str) -> bool:
    wl = load_cookie_whitelist()
    domain = domain.lstrip(".")
    for w in wl:
        if domain == w or domain.endswith("." + w):
            return True
    return False


# ---------------------------------------------------------------------------
# Site permissions
# ---------------------------------------------------------------------------

def load_permissions():
    """Load per-site permission decisions."""
    return _load_json("permissions.json", {})


def save_permissions(permissions):
    _save_json("permissions.json", permissions)


def get_permission(host, feature):
    """Get stored permission for host+feature. Returns 'allow', 'deny', or None."""
    perms = load_permissions()
    return perms.get(host, {}).get(feature)


def set_permission(host, feature, decision):
    """Store a permission decision ('allow' or 'deny') for host+feature."""
    perms = load_permissions()
    if host not in perms:
        perms[host] = {}
    perms[host][feature] = decision
    save_permissions(perms)


def remove_permission(host, feature=None):
    """Remove permission(s) for a host. If feature is None, remove all for that host."""
    perms = load_permissions()
    if host in perms:
        if feature:
            perms[host].pop(feature, None)
            if not perms[host]:
                del perms[host]
        else:
            del perms[host]
        save_permissions(perms)


# ---------------------------------------------------------------------------
# URL autocomplete suggestions
# ---------------------------------------------------------------------------

def get_url_suggestions(limit=500):
    """Return deduplicated URL suggestions sorted by visit frequency.

    Merges history and bookmarks.  Returns a list of
    ``(url, title, frequency)`` tuples, most-visited first, capped at *limit*.
    """
    freq = {}   # url -> visit count
    titles = {} # url -> most recent title

    for entry in load_history():
        url = entry.get("url", "")
        if not url or url.startswith("shroud:"):
            continue
        freq[url] = freq.get(url, 0) + 1
        if url not in titles:
            titles[url] = entry.get("title", "")

    for bm in load_bookmarks():
        url = bm.get("url", "")
        if not url:
            continue
        freq.setdefault(url, 0)
        if url not in titles or not titles[url]:
            titles[url] = bm.get("title", "")

    suggestions = [(url, titles.get(url, ""), count) for url, count in freq.items()]
    suggestions.sort(key=lambda t: t[2], reverse=True)
    return suggestions[:limit]
