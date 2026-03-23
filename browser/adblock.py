"""Host-based ad/tracker blocker with filter list support and tracking parameter stripping."""

import base64

from PyQt6.QtCore import QUrl, QUrlQuery
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from . import storage
from . import filterlists

# Hardcoded fallback domains (used even when no filter lists are downloaded)
DEFAULT_BLOCKED = {
    # Google
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "google-analytics.com",
    "googletagmanager.com",
    "analytics.google.com",
    "adservice.google.com",
    "pagead2.googlesyndication.com",
    "ad.doubleclick.net",
    # Facebook
    "facebook.net",
    "fbcdn.net",
    "an.facebook.com",
    "pixel.facebook.com",
    # Twitter / X
    "ads.twitter.com",
    "static.ads-twitter.com",
    "ads-api.twitter.com",
    # Yahoo / Omniture
    "ads.yahoo.com",
    "analytics.yahoo.com",
    "gemini.yahoo.com",
    "geo.yahoo.com",
    "partnerads.ysm.yahoo.com",
    "analytics.query.yahoo.com",
    "adtech.yahooinc.com",
    "udcm.yahoo.com",
    "log.fc.yahoo.com",
    "2o7.net",
    # Ad networks
    "advertising.com",
    "taboola.com",
    "outbrain.com",
    "scorecardresearch.com",
    "quantserve.com",
    "bluekai.com",
    "krxd.net",
    "exelator.com",
    "adnxs.com",
    "rubiconproject.com",
    "pubmatic.com",
    "openx.net",
    "casalemedia.com",
    "turn.com",
    "mathtag.com",
    "serving-sys.com",
    "eyeota.net",
    "agkn.com",
    "adsrvr.org",
    "demdex.net",
    "moatads.com",
    "cdn.ampproject.org",
    # Analytics services
    "hotjar.com",
    "hotjar.io",
    "mouseflow.com",
    "freshmarketer.com",
    "luckyorange.com",
    "luckyorange.net",
    # Error trackers
    "bugsnag.com",
    "sentry-cdn.com",
    "getsentry.com",
    # Social trackers
    "ads.linkedin.com",
    "analytics.pointdrive.linkedin.com",
    "trk.pinterest.com",
    "ads.pinterest.com",
    "log.pinterest.com",
    "events.redditmedia.com",
    "events.reddit.com",
    "ads.youtube.com",
    "analytics.tiktok.com",
    "analytics-sg.tiktok.com",
    "ads-api.tiktok.com",
    "ads.tiktok.com",
    "ads-sg.tiktok.com",
    "business-api.tiktok.com",
    "byteoversea.com",
    # Yandex
    "adfox.yandex.ru",
    "adfstat.yandex.ru",
    "appmetrica.yandex.ru",
    "metrika.yandex.ru",
    "extmaps-api.yandex.net",
    "offerwall.yandex.net",
    # Unity Ads
    "adserver.unityads.unity3d.com",
    "auction.unityads.unity3d.com",
    "config.unityads.unity3d.com",
    "webview.unityads.unity3d.com",
    # OEM trackers - Realme
    "iot-eu-logser.realme.com",
    "iot-logser.realme.com",
    "realmemobile.com",
    # OEM trackers - Xiaomi
    "api.ad.xiaomi.com",
    "data.mistat.xiaomi.com",
    "data.mistat.india.xiaomi.com",
    "data.mistat.rus.xiaomi.com",
    "sdkconfig.ad.xiaomi.com",
    "sdkconfig.ad.intl.xiaomi.com",
    "tracking.rus.miui.com",
    # OEM trackers - Oppo
    "oppomobile.com",
    # OEM trackers - Huawei
    "hicloud.com",
    # OEM trackers - OnePlus
    "open.oneplus.net",
    "click.oneplus.cn",
    # OEM trackers - Samsung
    "samsungads.com",
    "smetrics.samsung.com",
    "nmetrics.samsung.com",
    "samsung-com.112.2o7.net",
    "samsunghealthcn.com",
    # OEM trackers - Apple
    "iadsdk.apple.com",
    "metrics.icloud.com",
    "metrics.mzstatic.com",
    "weather-analytics-events.apple.com",
    "notes-analytics-events.apple.com",
    "api-adservices.apple.com",
    "books-analytics-events.apple.com",
    # Adcolony
    "adcolony.com",
    # Media.net
    "media.net",
    # Stats
    "stats.wp.com",
}

# Known tracking query parameters to strip
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_cid",
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid",
    "mc_eid", "oly_anon_id", "oly_enc_id",
    "__hssc", "__hstc", "__hsfp", "hsCtaTracking", "_hsenc",
    "_openstat", "vero_id", "wickedid", "yclid", "mkt_tok",
    "igshid", "si", "s_cid", "soc_src", "soc_trk",
    "ref_src", "ref_url", "_ga", "_gl",
}


class PageTracker:
    """Accumulated request data for a single first-party domain."""
    __slots__ = ('blocked', 'third_party', 'stripped_params')

    def __init__(self):
        self.blocked: dict[str, int] = {}       # host -> request count
        self.third_party: dict[str, int] = {}   # host -> request count (allowed)
        self.stripped_params: set[str] = set()


class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
        self._blocked_hosts = set()
        self._blocked_count = 0
        self.do_not_track = True
        self.strip_tracking = True
        self._http_auth = {}  # host -> b"Basic base64(user:pass)"
        self._page_data: dict[str, PageTracker] = {}
        self._site_exceptions: dict[str, dict[str, str]] = {}
        self.reload_hosts()

    def set_http_auth(self, host, user, password):
        """Cache HTTP Basic auth credentials for a host."""
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self._http_auth[host.lower()] = f"Basic {token}".encode()

    def clear_http_auth(self, host=None):
        """Clear cached auth credentials."""
        if host:
            self._http_auth.pop(host.lower(), None)
        else:
            self._http_auth.clear()

    def reload_hosts(self):
        """Merge hardcoded defaults + custom hosts + all enabled filter lists."""
        custom = storage.load_blocked_hosts()
        filter_hosts = filterlists.get_all_blocked_hosts()
        self._blocked_hosts = DEFAULT_BLOCKED | custom | filter_hosts

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value

    @property
    def blocked_count(self):
        return self._blocked_count

    @property
    def total_rules(self):
        return len(self._blocked_hosts)

    def reset_count(self):
        self._blocked_count = 0

    # ── per-page tracking for the Privacy Dashboard ──────────────

    def get_page_data(self, host):
        """Return PageTracker for a first-party host, or None."""
        return self._page_data.get(host.lower())

    def clear_page_data(self, host=None):
        """Clear tracked data for one or all hosts."""
        if host:
            self._page_data.pop(host.lower(), None)
        else:
            self._page_data.clear()

    def set_site_exceptions(self, exceptions):
        """Load per-site allow/block overrides from storage."""
        self._site_exceptions = exceptions or {}

    def _ensure_page_data(self, fp_host):
        tracker = self._page_data.get(fp_host)
        if tracker is None:
            tracker = PageTracker()
            self._page_data[fp_host] = tracker
        return tracker

    @staticmethod
    def _is_third_party(fp_host, req_host):
        if not fp_host or not req_host:
            return False
        fp = fp_host.removeprefix("www.")
        rq = req_host.removeprefix("www.")
        if fp == rq:
            return False
        return not (rq.endswith("." + fp) or fp.endswith("." + rq))

    def _match_blocked(self, host):
        """Return the blocked domain rule that matches *host*, or None."""
        parts = host.split(".")
        for i in range(len(parts) - 1):
            domain = ".".join(parts[i:])
            if domain in self._blocked_hosts:
                return domain
        return None

    def interceptRequest(self, info):
        # Inject Do Not Track header
        if self.do_not_track:
            info.setHttpHeader(b"DNT", b"1")

        url = info.requestUrl()
        req_host = url.host().lower()

        # Inject HTTP Basic auth header for protected hosts
        auth = self._http_auth.get(req_host)
        if auth:
            info.setHttpHeader(b"Authorization", auth)

        # Strip cross-origin referrers to origin only
        if self.do_not_track:
            info.setHttpHeader(b"Referrer-Policy", b"strict-origin-when-cross-origin")

        # Determine first-party context for per-page tracking
        # Skip tracking for internal shroud:// pages
        if url.scheme() == "shroud":
            return
        first_party = info.firstPartyUrl()
        fp_scheme = first_party.scheme() if first_party.isValid() else ""
        fp_host = (first_party.host() or "").lower() if first_party.isValid() else ""
        if fp_scheme == "shroud":
            fp_host = ""  # don't track internal pages
        is_3p = self._is_third_party(fp_host, req_host)

        # Strip tracking parameters from URLs
        if self.strip_tracking and url.hasQuery():
            query = QUrlQuery(url)
            items = query.queryItems()
            cleaned = [(k, v) for k, v in items if k not in TRACKING_PARAMS]
            if len(cleaned) < len(items):
                # Record stripped params
                if fp_host:
                    tracker = self._ensure_page_data(fp_host)
                    for k, v in items:
                        if k in TRACKING_PARAMS:
                            tracker.stripped_params.add(k)
                clean_url = QUrl(url)
                if cleaned:
                    new_query = QUrlQuery()
                    for k, v in cleaned:
                        new_query.addQueryItem(k, v)
                    clean_url.setQuery(new_query)
                else:
                    clean_url.setQuery("")
                info.redirect(clean_url)
                return

        if not self._enabled:
            # Still track third-party connections when blocker is off
            if is_3p and fp_host:
                tracker = self._ensure_page_data(fp_host)
                tracker.third_party[req_host] = tracker.third_party.get(req_host, 0) + 1
            return

        # Check per-site exceptions before normal blocking
        if is_3p and fp_host:
            site_exc = self._site_exceptions.get(fp_host, {})
            exc = site_exc.get(req_host)
            if exc == "allow":
                tracker = self._ensure_page_data(fp_host)
                tracker.third_party[req_host] = tracker.third_party.get(req_host, 0) + 1
                return  # user-allowed override
            if exc == "block":
                tracker = self._ensure_page_data(fp_host)
                tracker.blocked[req_host] = tracker.blocked.get(req_host, 0) + 1
                info.block(True)
                self._blocked_count += 1
                return  # user-blocked override

        # Check if the host or any parent domain is blocked
        if self._match_blocked(req_host):
            if is_3p and fp_host:
                tracker = self._ensure_page_data(fp_host)
                tracker.blocked[req_host] = tracker.blocked.get(req_host, 0) + 1
            info.block(True)
            self._blocked_count += 1
            return

        # Not blocked — record as third-party if applicable
        if is_3p and fp_host:
            tracker = self._ensure_page_data(fp_host)
            tracker.third_party[req_host] = tracker.third_party.get(req_host, 0) + 1
