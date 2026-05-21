package com.shroudbyte.adblock

import android.net.Uri

/**
 * Cheap, fast host-list adblocker. We can't intercept WebView subresource
 * loads as richly as Chromium's request interceptor, but [shouldBlock]
 * gives us enough surface for `shouldInterceptRequest` to drop calls to
 * known tracker domains.
 *
 * A future Tier-2 port would bring over the full ABP filter engine from
 * `browser/adblock_engine.py`; for now we cover the 80/20 case.
 */
class HostBlocker(initialHosts: Set<String> = DEFAULT_HOSTS) {

    @Volatile private var hosts: Set<String> = initialHosts.map { it.lowercase() }.toSet()

    fun setHosts(newHosts: Set<String>) {
        hosts = newHosts.map { it.lowercase() }.toSet()
    }

    /**
     * True if a request to [url] should be blocked. Matches the request
     * host AND every parent domain so a single `doubleclick.net` entry
     * also covers `ad.doubleclick.net`.
     */
    fun shouldBlock(url: String): Boolean {
        val host = try {
            Uri.parse(url).host?.lowercase()
        } catch (_: Exception) {
            return false
        } ?: return false

        if (host in hosts) return true
        var idx = host.indexOf('.')
        while (idx in 0 until host.length - 1) {
            if (host.substring(idx + 1) in hosts) return true
            idx = host.indexOf('.', idx + 1)
        }
        return false
    }

    companion object {
        /**
         * Tiny starter list — same shape as DEFAULT_BLOCKED in
         * `browser/adblock.py`. Production builds should ship the real
         * EasyList/EasyPrivacy host lists, downloaded at first launch.
         */
        val DEFAULT_HOSTS: Set<String> = setOf(
            "doubleclick.net",
            "google-analytics.com",
            "googletagmanager.com",
            "googletagservices.com",
            "googlesyndication.com",
            "googleadservices.com",
            "facebook.net",
            "connect.facebook.net",
            "scorecardresearch.com",
            "quantserve.com",
            "outbrain.com",
            "taboola.com",
            "criteo.com",
            "criteo.net",
            "adnxs.com",
            "rubiconproject.com",
            "amazon-adsystem.com",
            "moatads.com",
            "adsrvr.org",
            "advertising.com",
            "branch.io",
            "hotjar.com",
            "mixpanel.com",
            "segment.io",
            "fullstory.com",
        )
    }
}

/**
 * Tracking-parameter stripping — `utm_*`, `fbclid`, etc. Same list as
 * `browser/adblock.py:TRACKING_PARAMS`.
 */
object TrackingParams {
    val NAMES: Set<String> = setOf(
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "utm_name", "utm_brand", "utm_social", "utm_social-type",
        "fbclid", "gclid", "msclkid", "dclid", "yclid", "twclid",
        "mc_eid", "mc_cid", "_hsenc", "_hsmi",
        "vero_conv", "vero_id", "wickedid",
        "oly_anon_id", "oly_enc_id",
        "rb_clickid", "s_cid", "soc_src", "soc_trk",
        "ref_src", "ref_url", "_ga", "_gl",
        "igshid", "si",
    )

    /** Return [url] with known tracking params removed; leaves everything else intact. */
    fun strip(url: String): String {
        val uri = try { Uri.parse(url) } catch (_: Exception) { return url }
        val query = uri.query ?: return url
        val kept = query.split("&").mapNotNull { kv ->
            val eq = kv.indexOf('=')
            val name = if (eq < 0) kv else kv.substring(0, eq)
            if (name.lowercase() in NAMES) null else kv
        }
        val rebuiltQuery = kept.joinToString("&")
        val builder = uri.buildUpon().clearQuery()
        if (rebuiltQuery.isNotEmpty()) builder.encodedQuery(rebuiltQuery)
        return builder.build().toString()
    }
}
