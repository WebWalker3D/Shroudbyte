"""Host-based ad/tracker blocker with filter list support and tracking parameter stripping."""

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


class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
        self._blocked_hosts = set()
        self._blocked_count = 0
        self.do_not_track = True
        self.strip_tracking = True
        self.reload_hosts()

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

    def interceptRequest(self, info):
        # Inject Do Not Track header
        if self.do_not_track:
            info.setHttpHeader(b"DNT", b"1")

        url = info.requestUrl()

        # Strip tracking parameters from URLs
        if self.strip_tracking and url.hasQuery():
            query = QUrlQuery(url)
            items = query.queryItems()
            cleaned = [(k, v) for k, v in items if k not in TRACKING_PARAMS]
            if len(cleaned) < len(items):
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
            return

        host = url.host().lower()
        # Check if the host or any parent domain is blocked
        parts = host.split(".")
        for i in range(len(parts) - 1):
            domain = ".".join(parts[i:])
            if domain in self._blocked_hosts:
                info.block(True)
                self._blocked_count += 1
                return
