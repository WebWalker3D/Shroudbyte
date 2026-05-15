"""Optional update checker.

Hits the GitHub Releases API for the upstream repo, compares against
:data:`browser.__version__`, and caches the answer for 24h so we don't
hammer GitHub. Opt-in: disabled unless ``check_for_updates`` is set to
True in settings.
"""

from __future__ import annotations

import json
import logging
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__, storage


logger = logging.getLogger("shroudbyte.updater")

_REPO = "WebWalker3D/Shroudbyte"
_CACHE_FILE = "update_check.json"
_CACHE_TTL = 24 * 3600


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a 'v1.2.3' / '1.2.3' style version into a tuple of ints.

    Falls back to (0,) on unparsable input so the caller treats it as the
    oldest possible version (i.e. always "older than current").
    """
    nums = re.findall(r"\d+", v or "")
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums[:4])


def _cache_path() -> Path:
    return storage.DATA_DIR / _CACHE_FILE


def _load_cache() -> dict:
    try:
        path = _cache_path()
        if path.exists():
            return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read update cache: %s", e)
    return {}


def _save_cache(data: dict):
    try:
        storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path().write_text(json.dumps(data))
    except OSError as e:
        logger.warning("Could not write update cache: %s", e)


def check_for_update(force: bool = False) -> dict | None:
    """Check GitHub for a newer release.

    Returns ``None`` on network failure or if no newer version exists.
    Otherwise returns ``{"latest", "current", "url", "notes"}``.

    Honors a 24h cache unless ``force`` is True.
    """
    cache = _load_cache()
    now = time.time()
    if not force and cache.get("checked_at", 0) + _CACHE_TTL > now:
        return cache.get("result")

    url = f"https://api.github.com/repos/{_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"Shroudbyte/{__version__}",
            },
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 404 just means no releases yet; cache the negative result so
        # we don't retry every startup.
        logger.info("Update check HTTP %s for %s", e.code, url)
        _save_cache({"checked_at": now, "result": None})
        return None
    except Exception as e:
        logger.warning("Update check failed: %s", e)
        return None

    latest = payload.get("tag_name", "") or payload.get("name", "")
    result = None
    if latest and _parse_version(latest) > _parse_version(__version__):
        result = {
            "latest": latest.lstrip("v"),
            "current": __version__,
            "url": payload.get("html_url", f"https://github.com/{_REPO}/releases"),
            "notes": (payload.get("body") or "")[:500],
        }
    _save_cache({"checked_at": now, "result": result})
    return result


def maybe_check_in_background(settings: dict):
    """Fire-and-forget update check if the user opted in.

    Safe to call from the GUI thread; runs the actual network call on a
    background thread.
    """
    if not settings.get("check_for_updates", False):
        return
    import threading
    threading.Thread(
        target=check_for_update, kwargs={"force": False}, daemon=True
    ).start()
