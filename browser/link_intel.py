"""Link Intelligence — pre-navigation redirect chain resolver.

Resolves the full redirect chain for hovered URLs before the user clicks,
revealing the true destination, tracker domains, URL shorteners, and
tracking parameters that would be stripped.
"""

import concurrent.futures
import http.client
import ssl
import threading
import urllib.parse

from .adblock import DEFAULT_BLOCKED, TRACKING_PARAMS

# Known URL shortener / redirect service domains
SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "bl.ink", "lnkd.in", "rb.gy", "cutt.ly",
    "t.ly", "shorturl.at", "tiny.cc", "surl.li", "rebrand.ly",
    "clck.ru", "short.io", "dub.sh", "amzn.to", "amzn.eu",
    "youtu.be", "redd.it", "v.gd", "qr.ae", "shor.by", "trib.al",
    "dlvr.it", "ift.tt", "j.mp", "soo.gd", "s.id", "rotf.lol",
}

MAX_REDIRECTS = 10
TIMEOUT_PER_HOP = 2.5  # seconds
CACHE_MAX = 512


class LinkResolver:
    """Resolves redirect chains for hovered URLs in background threads."""

    def __init__(self, blocked_hosts=None):
        self._blocked = blocked_hosts or DEFAULT_BLOCKED
        self._cache: dict = {}
        self._lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def update_blocked_hosts(self, hosts):
        """Update the set of known tracker/ad domains."""
        self._blocked = hosts

    def resolve(self, url, callback):
        """Resolve *url*'s redirect chain in a background thread.

        *callback(result_dict)* is invoked from the **worker** thread —
        callers must marshal to the GUI thread themselves (e.g. QTimer).
        """
        with self._lock:
            cached = self._cache.get(url)
            if cached is not None:
                callback(cached)
                return

        self._executor.submit(self._worker, url, callback)

    # ── internals ────────────────────────────────────────────────

    def _worker(self, url, callback):
        result = self._follow(url)
        with self._lock:
            # Simple cache eviction — drop oldest quarter when full
            if len(self._cache) >= CACHE_MAX:
                for k in list(self._cache)[:CACHE_MAX // 4]:
                    del self._cache[k]
            self._cache[url] = result
        callback(result)

    def _follow(self, url):
        chain = []
        trackers = []
        tracking_params = set()
        is_shortener = False
        current = url

        for _ in range(MAX_REDIRECTS):
            parsed = urllib.parse.urlparse(current)
            host = (parsed.hostname or "").lower()

            # Detect shortener
            if host in SHORTENER_DOMAINS:
                is_shortener = True

            # Detect tracker domain
            parts = host.split(".")
            for i in range(len(parts) - 1):
                if ".".join(parts[i:]) in self._blocked:
                    if host not in trackers:
                        trackers.append(host)
                    break

            # Detect tracking params
            if parsed.query:
                for key, _ in urllib.parse.parse_qsl(
                    parsed.query, keep_blank_values=True
                ):
                    if key in TRACKING_PARAMS:
                        tracking_params.add(key)

            # HEAD request to follow redirect
            try:
                conn = self._connect(parsed)
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                conn.request("HEAD", path, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "*/*",
                })
                resp = conn.getresponse()
                conn.close()
            except Exception:
                break

            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location")
                if location:
                    chain.append(current)
                    current = urllib.parse.urljoin(current, location)
                    continue

            break  # 200 or non-redirect

        # Check final URL for tracking params
        final_parsed = urllib.parse.urlparse(current)
        if final_parsed.query:
            for key, _ in urllib.parse.parse_qsl(
                final_parsed.query, keep_blank_values=True
            ):
                if key in TRACKING_PARAMS:
                    tracking_params.add(key)

        return {
            "href": url,
            "final": current,
            "chain": chain,
            "redirects": len(chain),
            "trackers": trackers,
            "tracking_params": sorted(tracking_params),
            "shortener": is_shortener,
        }

    @staticmethod
    def _connect(parsed):
        if parsed.scheme == "https":
            ctx = ssl.create_default_context()
            return http.client.HTTPSConnection(
                parsed.hostname, parsed.port or 443,
                context=ctx, timeout=TIMEOUT_PER_HOP,
            )
        return http.client.HTTPConnection(
            parsed.hostname, parsed.port or 80,
            timeout=TIMEOUT_PER_HOP,
        )
