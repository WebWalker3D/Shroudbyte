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

_json_cache: dict = {}


def _load_json(filename, default=None):
    if filename in _json_cache:
        return _json_cache[filename]
    _ensure_dir()
    path = DATA_DIR / filename
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        _json_cache[filename] = data
        return data
    result = default if default is not None else []
    _json_cache[filename] = result
    return result


def _save_json(filename, data):
    _ensure_dir()
    _json_cache[filename] = data
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, separators=(',', ':'))


def invalidate_cache(filename=None):
    """Clear the in-memory JSON cache. If filename given, clear only that entry."""
    if filename:
        _json_cache.pop(filename, None)
    else:
        _json_cache.clear()


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------

def load_bookmarks():
    return _load_json("bookmarks.json", [])


def save_bookmarks(bookmarks):
    _save_json("bookmarks.json", bookmarks)


def add_bookmark(title, url, folder="", tags=None):
    bm = load_bookmarks()
    if any(b["url"] == url for b in bm):
        return False  # duplicate detection
    bm.append({
        "title": title, "url": url, "added": time.time(),
        "folder": folder, "tags": tags or [],
    })
    save_bookmarks(bm)
    return True


def remove_bookmark(url):
    bm = load_bookmarks()
    bm = [b for b in bm if b["url"] != url]
    save_bookmarks(bm)


def update_bookmark(url, title=None, folder=None, tags=None):
    """Update fields of an existing bookmark by URL."""
    bm = load_bookmarks()
    for b in bm:
        if b["url"] == url:
            if title is not None:
                b["title"] = title
            if folder is not None:
                b["folder"] = folder
            if tags is not None:
                b["tags"] = tags
            break
    save_bookmarks(bm)


def render_netscape_bookmarks(bookmarks: list[dict]) -> str:
    """Render a bookmark list back into Netscape HTML, preserving folders.

    Each bookmark's ``folder`` field is treated as a forward-slash-joined
    path. Bookmarks with empty/missing folder land at the top level.
    """
    import html as _html
    import time as _time

    # Build a nested tree: {"_items": [...], "<folder_name>": {...}}.
    Tree = dict
    root: Tree = {"_items": []}

    def _ensure_path(parts: list[str]) -> Tree:
        node = root
        for part in parts:
            if part not in node:
                node[part] = {"_items": []}
            node = node[part]
        return node

    for bm in bookmarks:
        folder = (bm.get("folder") or "").strip("/")
        parts = [p for p in folder.split("/") if p] if folder else []
        node = _ensure_path(parts)
        node["_items"].append(bm)

    out: list[str] = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
        "<DL><p>",
    ]

    def _emit(node: Tree, depth: int):
        indent = "    " * depth
        for bm in node["_items"]:
            ts = int(bm.get("added", _time.time()))
            title = _html.escape(bm.get("title", ""))
            url = _html.escape(bm.get("url", ""))
            out.append(f'{indent}<DT><A HREF="{url}" ADD_DATE="{ts}">{title}</A>')
        for key, child in node.items():
            if key == "_items":
                continue
            out.append(f"{indent}<DT><H3>{_html.escape(key)}</H3>")
            out.append(f"{indent}<DL><p>")
            _emit(child, depth + 1)
            out.append(f"{indent}</DL><p>")

    _emit(root, 1)
    out.append("</DL><p>")
    return "\n".join(out)


def parse_netscape_bookmarks(content: str) -> list[dict]:
    """Parse Netscape bookmark HTML, preserving folder nesting.

    Returns a list of {title, url, folder} dicts where folder is a
    forward-slash-joined path (empty string for top-level entries).
    """
    import html as _html
    import re as _re
    token_pattern = _re.compile(
        r'<H3[^>]*>([^<]*)</H3>'
        r'|<A\s+HREF="([^"]+)"[^>]*>([^<]*)</A>'
        r'|</DL>',
        _re.IGNORECASE,
    )
    folder_stack: list[str] = []
    results: list[dict] = []
    for m in token_pattern.finditer(content):
        folder_name, url, title = m.group(1), m.group(2), m.group(3)
        if folder_name is not None:
            folder_stack.append(_html.unescape(folder_name.strip()))
        elif url is not None:
            results.append({
                "title": _html.unescape((title or "").strip()),
                "url": _html.unescape(url.strip()),
                "folder": "/".join(folder_stack),
            })
        else:
            if folder_stack:
                folder_stack.pop()
    return results


def get_bookmark_folders() -> list[str]:
    """Return sorted list of unique folder paths."""
    folders = set()
    for bm in load_bookmarks():
        f = bm.get("folder", "")
        if f:
            folders.add(f)
    return sorted(folders)


def get_bookmark_tags() -> list[str]:
    """Return sorted list of unique tags."""
    tags = set()
    for bm in load_bookmarks():
        for t in bm.get("tags", []):
            tags.add(t)
    return sorted(tags)


def is_bookmarked(url):
    return any(b["url"] == url for b in load_bookmarks())


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def load_history():
    from .db import get_db
    return get_db().load_history()


def add_history_entry(title, url):
    from .db import get_db
    get_db().add_history_entry(title, url)


def clear_history():
    from .db import get_db
    get_db().clear_history()


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
    "https_only": True,
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
    "link_intelligence": True,
    "page_watch_interval": 3600,
    "remember_scroll_position": True,
    "form_draft_autosave": True,
    "annoyance_shield": True,
    "screen_time_tracking": False,
    "clipboard_history": True,
    "vault_auto_lock_minutes": 15,
    "permission_ttl_days": 30,
    "dark_mode": True,
    "wallpaper": "",
    "search_suggestions": False,
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
# Window state (geometry + maximized/fullscreen) for restore on next launch
# ---------------------------------------------------------------------------

def save_window_state(state: dict):
    """Persist window state dict {state, x, y, width, height}."""
    _save_json("window_state.json", state)


def load_window_state() -> dict:
    """Return saved window state dict, or {} if none."""
    return _load_json("window_state.json", {})


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
    entry = perms.get(host, {}).get(feature)
    if entry is None:
        return None
    # Support both old format (bare string) and new format (dict)
    if isinstance(entry, str):
        return entry  # legacy, no expiry
    expires = entry.get("expires_at", 0)
    if expires > 0 and time.time() > expires:
        # Expired — remove and re-prompt next time
        remove_permission(host, feature)
        return None
    return entry.get("decision")


def set_permission(host, feature, decision, ttl_days=30):
    """Store a permission decision ('allow' or 'deny') for host+feature.

    If *ttl_days* > 0 the permission will automatically expire after the
    given number of days.  A value of 0 means the permission never expires.
    """
    perms = load_permissions()
    if host not in perms:
        perms[host] = {}
    now = time.time()
    perms[host][feature] = {
        "decision": decision,
        "granted_at": now,
        "expires_at": now + (ttl_days * 86400) if ttl_days > 0 else 0,
    }
    save_permissions(perms)


def remove_all_permissions(host):
    """Remove all permissions for a host."""
    perms = load_permissions()
    if host in perms:
        del perms[host]
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
# Site-specific tracker exceptions (Privacy Dashboard)
# ---------------------------------------------------------------------------

def load_site_exceptions():
    """Load per-site tracker allow/block overrides.

    Returns ``{site_host: {tracker_host: "allow"|"block", ...}, ...}``.
    """
    return _load_json("site_exceptions.json", {})


def save_site_exceptions(exceptions):
    _save_json("site_exceptions.json", exceptions)


def set_site_exception(site_host, tracker_host, action):
    """Set a per-site exception ('allow' or 'block') for a tracker domain."""
    exc = load_site_exceptions()
    if site_host not in exc:
        exc[site_host] = {}
    exc[site_host][tracker_host] = action
    save_site_exceptions(exc)


def remove_site_exception(site_host, tracker_host):
    """Remove a per-site exception."""
    exc = load_site_exceptions()
    if site_host in exc:
        exc[site_host].pop(tracker_host, None)
        if not exc[site_host]:
            del exc[site_host]
        save_site_exceptions(exc)


# ---------------------------------------------------------------------------
# Page Watches
# ---------------------------------------------------------------------------

def load_watches():
    return _load_json("watches.json", [])


def save_watches(watches):
    _save_json("watches.json", watches)


def add_watch(url, title, interval=3600):
    watches = load_watches()
    if any(w["url"] == url for w in watches):
        return False
    watches.append({
        "url": url, "title": title, "interval": interval,
        "enabled": True, "created": time.time(),
        "last_check": 0, "last_changed": 0,
        "last_snapshot": "", "last_diff": "",
        "change_count": 0,
    })
    save_watches(watches)
    return True


def remove_watch(url):
    watches = load_watches()
    watches = [w for w in watches if w["url"] != url]
    save_watches(watches)


def is_watched(url):
    return any(w["url"] == url for w in load_watches())


def update_watch(url, updates):
    """Update fields of a specific watch by URL."""
    watches = load_watches()
    for w in watches:
        if w["url"] == url:
            w.update(updates)
            break
    save_watches(watches)


# ---------------------------------------------------------------------------
# Scroll position memory
# ---------------------------------------------------------------------------

def get_scroll_position(url: str) -> float:
    """Return saved scroll percentage (0.0–1.0) for a URL, or 0."""
    from .db import get_db
    return get_db().get_scroll_position(url)


def set_scroll_position(url: str, position: float):
    """Save scroll percentage for a URL."""
    from .db import get_db
    get_db().set_scroll_position(url, position)


# ---------------------------------------------------------------------------
# Form draft auto-save
# ---------------------------------------------------------------------------

def get_form_draft(url: str) -> dict | None:
    """Return saved draft for a URL, or None."""
    from .db import get_db
    return get_db().get_form_draft(url)


def save_form_draft(url: str, fields: dict, timestamp: float | None = None):
    """Save form field values for a URL."""
    from .db import get_db
    get_db().save_form_draft(url, fields, timestamp)


def remove_form_draft(url: str):
    from .db import get_db
    get_db().remove_form_draft(url)


# ---------------------------------------------------------------------------
# Screen time tracking
# ---------------------------------------------------------------------------

def load_screen_time() -> dict:
    """Load screen time data. Returns {domain: {date_str: seconds}}."""
    from .db import get_db
    return get_db().load_screen_time()


def add_screen_time(domain: str, date_str: str, seconds: int):
    """Add seconds to a domain's time for a given date."""
    from .db import get_db
    get_db().add_screen_time(domain, date_str, seconds)


def clear_screen_time():
    from .db import get_db
    get_db().clear_screen_time()


# ---------------------------------------------------------------------------
# Installed PWAs (Progressive Web Apps)
# ---------------------------------------------------------------------------

def load_installed_apps() -> list[dict]:
    return _load_json("installed_apps.json", [])


def save_installed_apps(apps: list[dict]):
    _save_json("installed_apps.json", apps)


def add_installed_app(app: dict):
    apps = load_installed_apps()
    # Replace existing with same start_url
    apps = [a for a in apps if a.get("start_url") != app.get("start_url")]
    apps.insert(0, app)
    save_installed_apps(apps)


def remove_installed_app(start_url: str):
    apps = load_installed_apps()
    apps = [a for a in apps if a.get("start_url") != start_url]
    save_installed_apps(apps)


def get_installed_app(start_url: str) -> dict | None:
    for a in load_installed_apps():
        if a.get("start_url") == start_url:
            return a
    return None


# ---------------------------------------------------------------------------
# Saved pages (offline snapshots)
# ---------------------------------------------------------------------------

import hashlib

_SAVED_DIR = DATA_DIR / "saved"


def load_saved_pages() -> list[dict]:
    """Return list of saved page metadata, newest first."""
    return _load_json("saved_pages.json", [])


def save_page(url: str, title: str, html: str, text_preview: str = ""):
    """Save a page snapshot. Stores HTML in a separate file."""
    _ensure_dir()
    _SAVED_DIR.mkdir(parents=True, exist_ok=True)

    page_id = hashlib.sha256(url.encode()).hexdigest()[:16]
    html_path = _SAVED_DIR / f"{page_id}.html"
    html_path.write_text(html, encoding="utf-8")

    pages = load_saved_pages()
    # Remove existing snapshot of the same URL (re-save updates it)
    pages = [p for p in pages if p.get("url") != url]
    pages.insert(0, {
        "id": page_id,
        "url": url,
        "title": title,
        "preview": text_preview[:200],
        "saved": time.time(),
        "size": len(html),
    })
    _save_json("saved_pages.json", pages)


def get_saved_page_html(page_id: str) -> str:
    """Return the HTML content of a saved page."""
    path = _SAVED_DIR / f"{page_id}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def remove_saved_page(page_id: str):
    """Delete a saved page snapshot."""
    path = _SAVED_DIR / f"{page_id}.html"
    if path.exists():
        path.unlink()
    pages = load_saved_pages()
    pages = [p for p in pages if p.get("id") != page_id]
    _save_json("saved_pages.json", pages)


# ---------------------------------------------------------------------------
# URL autocomplete suggestions
# ---------------------------------------------------------------------------

def get_url_suggestions(limit=500):
    """Return deduplicated URL suggestions sorted by visit frequency.

    Merges history and bookmarks.  Returns a list of
    ``(url, title, frequency)`` tuples, most-visited first, capped at *limit*.
    """
    from .db import get_db
    return get_db().get_url_suggestions(limit)
