"""Downloadable filter list management for Blade Browser ad/tracker blocking.

Supports both hosts-file format and ABP/adblock-plus rule format.
Extracts domain blocks and cosmetic (CSS) hiding rules.
"""

import json
import os
import re
import time
import urllib.request
from pathlib import Path

from .storage import DATA_DIR, _ensure_dir, _load_json, _save_json

FILTERS_DIR = DATA_DIR / "filters"
SETTINGS_FILE = "filter_settings.json"

# --- Available filter lists ---------------------------------------------------

FILTER_LISTS = [
    {
        "id": "easylist",
        "name": "EasyList",
        "description": "Primary ad-blocking list. Removes most banner, sidebar, and popup ads.",
        "url": "https://easylist.to/easylist/easylist.txt",
        "enabled_default": True,
    },
    {
        "id": "easyprivacy",
        "name": "EasyPrivacy",
        "description": "Blocks tracking scripts, pixels, and analytics. Prevents sites from profiling your browsing.",
        "url": "https://easylist.to/easylist/easyprivacy.txt",
        "enabled_default": True,
    },
    {
        "id": "fanboy_annoyance",
        "name": "Fanboy's Annoyance List",
        "description": "Removes cookie notices, newsletter popups, and other page annoyances.",
        "url": "https://secure.fanboy.co.nz/fanboy-annoyance.txt",
        "enabled_default": True,
    },
    {
        "id": "fanboy_social",
        "name": "Fanboy's Social Blocking",
        "description": "Blocks social media widgets, share buttons, and like counters embedded on sites.",
        "url": "https://easylist.to/easylist/fanboy-social.txt",
        "enabled_default": False,
    },
    {
        "id": "peter_lowe",
        "name": "Peter Lowe's Ad Server List",
        "description": "Lightweight domain-level blocklist of known ad servers. Very low false-positive rate.",
        "url": "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0",
        "enabled_default": True,
    },
    {
        "id": "urlhaus",
        "name": "URLhaus Malicious URL Blocklist",
        "description": "Blocks known malware distribution sites. Protects against drive-by downloads.",
        "url": "https://urlhaus.abuse.ch/downloads/hostfile/",
        "enabled_default": True,
    },
]

# Hardcoded cookie banner selectors as a fallback
COOKIE_BANNER_SELECTORS = [
    "#cookie-banner",
    ".cookie-banner",
    ".cookie-consent",
    "#cookie-consent",
    "#gdpr-banner",
    ".gdpr-banner",
    "#onetrust-banner-sdk",
    "#onetrust-consent-sdk",
    ".cc-window",
    ".cc-banner",
    ".cmp-container",
    "#sp_message_container",
    "#CybotCookiebotDialog",
    ".qc-cmp-ui-container",
    '[class*="cookie-banner"]',
    '[id*="cookie-consent"]',
    '[class*="cookie-notice"]',
    '[id*="cookie-notice"]',
    '[class*="consent-banner"]',
    ".js-cookie-consent",
    "#cookieNotice",
    ".cookie-policy-popup",
]

# Hardcoded common ad element selectors as a fallback
AD_ELEMENT_SELECTORS = [
    # Generic ad containers
    ".ad", ".ads", ".ad-banner", ".ad-container", ".ad-wrapper",
    ".ad-slot", ".ad-unit", ".ad-block", ".ad-frame", ".ad-placeholder",
    "#ad", "#ads", "#ad-banner", "#ad-container", "#ad-wrapper",
    '[id^="ad-"]', '[class^="ad-"]', '[id^="ads-"]', '[class^="ads-"]',
    # Google Ads
    ".adsbygoogle", "ins.adsbygoogle",
    '[id^="google_ads"]', '[id^="div-gpt-ad"]',
    # Common ad class patterns
    '[class*="ad-slot"]', '[class*="ad-unit"]', '[class*="advert"]',
    '[id*="ad-slot"]', '[id*="ad-unit"]', '[id*="advert"]',
    ".advertisement", ".advertising", "#advertisement",
    ".sponsored", ".sponsor-ad",
    # Banner ads
    ".banner-ad", ".banner-ads", "#banner-ad",
    ".top-ad", ".bottom-ad", ".side-ad",
    ".leaderboard-ad", ".rectangle-ad", ".skyscraper-ad",
    # Social widgets
    ".fb-like", ".twitter-share", ".social-widget",
]

# --- List enable/disable settings --------------------------------------------

def load_list_settings() -> dict:
    """Return {list_id: bool} for each list's enabled state."""
    saved = _load_json(SETTINGS_FILE, {})
    result = {}
    for fl in FILTER_LISTS:
        result[fl["id"]] = saved.get(fl["id"], fl["enabled_default"])
    return result


def save_list_settings(settings: dict):
    _save_json(SETTINGS_FILE, settings)


# --- Download and cache -------------------------------------------------------

def _ensure_filters_dir():
    FILTERS_DIR.mkdir(parents=True, exist_ok=True)


def download_list(list_id: str, timeout: int = 30) -> bool:
    """Download a filter list and cache it locally. Returns True on success."""
    info = next((fl for fl in FILTER_LISTS if fl["id"] == list_id), None)
    if not info:
        return False
    _ensure_filters_dir()
    try:
        req = urllib.request.Request(
            info["url"],
            headers={"User-Agent": "BladeBrowser/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
        (FILTERS_DIR / f"{list_id}.txt").write_text(data, encoding="utf-8")
        return True
    except Exception:
        return False


def download_all_enabled(callback=None) -> dict:
    """Download all enabled lists. Returns {list_id: success_bool}.
    Optional callback(list_id, success) called after each download.
    """
    settings = load_list_settings()
    results = {}
    for fl in FILTER_LISTS:
        if settings.get(fl["id"], False):
            ok = download_list(fl["id"])
            results[fl["id"]] = ok
            if callback:
                callback(fl["id"], ok)
    return results


def get_cached_path(list_id: str) -> Path:
    return FILTERS_DIR / f"{list_id}.txt"


def is_cached(list_id: str) -> bool:
    return get_cached_path(list_id).exists()


# --- Parsing ------------------------------------------------------------------

def _parse_file(text: str) -> tuple[set, list]:
    """Parse a filter file (hosts or ABP format).
    Returns (blocked_domains, cosmetic_selectors).
    """
    domains = set()
    cosmetic = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("!", "#", "[")):
            # Comment or header
            # But check for cosmetic rules: ##selector
            pass

        # Hosts file format: 0.0.0.0 domain  or  127.0.0.1 domain
        if line.startswith(("0.0.0.0 ", "127.0.0.1 ")):
            parts = line.split()
            if len(parts) >= 2:
                domain = parts[1].strip().lower()
                if domain and domain != "localhost" and "." in domain:
                    domains.add(domain)
            continue

        # ABP domain block: ||domain^
        m = re.match(r'^\|\|([a-zA-Z0-9._-]+)\^(\$.*)?$', line)
        if m:
            domain = m.group(1).lower()
            if "." in domain:
                domains.add(domain)
            continue

        # ABP cosmetic filter: ##selector or site##selector (generic only)
        if "##" in line and not line.startswith("!"):
            parts = line.split("##", 1)
            if len(parts) == 2:
                domain_part = parts[0].strip()
                selector = parts[1].strip()
                # Only use generic rules (no domain prefix) or very common ones
                if not domain_part and selector and not selector.startswith("+"):
                    # Skip procedural filters (:has, :contains, etc.)
                    if ":has(" not in selector and ":contains(" not in selector:
                        cosmetic.append(selector)
            continue

    return domains, cosmetic


def get_all_blocked_hosts() -> set:
    """Return the merged set of blocked domains from all enabled, cached lists."""
    settings = load_list_settings()
    all_domains = set()
    for fl in FILTER_LISTS:
        if not settings.get(fl["id"], False):
            continue
        path = get_cached_path(fl["id"])
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            domains, _ = _parse_file(text)
            all_domains |= domains
        except Exception:
            continue
    return all_domains


def get_cosmetic_rules() -> list:
    """Return merged list of CSS selectors to hide from all enabled lists,
    plus hardcoded cookie banner selectors.
    """
    settings = load_list_settings()
    all_selectors = list(COOKIE_BANNER_SELECTORS) + list(AD_ELEMENT_SELECTORS)
    for fl in FILTER_LISTS:
        if not settings.get(fl["id"], False):
            continue
        path = get_cached_path(fl["id"])
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            _, cosmetic = _parse_file(text)
            all_selectors.extend(cosmetic)
        except Exception:
            continue
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in all_selectors:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def get_cosmetic_css() -> str:
    """Return a CSS string that hides all cosmetic-filtered elements."""
    rules = get_cosmetic_rules()
    if not rules:
        return ""
    # Batch selectors into groups to avoid overly long single rules
    batch_size = 50
    css_parts = []
    for i in range(0, len(rules), batch_size):
        batch = rules[i:i + batch_size]
        selector = ", ".join(batch)
        css_parts.append(f"{selector} {{ display: none !important; }}")
    return "\n".join(css_parts)


def get_total_domain_count() -> int:
    """Return total number of unique blocked domains across all enabled lists."""
    return len(get_all_blocked_hosts())
