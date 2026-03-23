"""Annoyance Shield — kills overlays, modals, consent popups, chat widgets, and attention-hijacking dark patterns.

Goes beyond ad blocking to handle the modern web's non-ad annoyances:
modal overlays, cookie consent SDKs, newsletter popups, chat widgets,
floating video players, anti-adblock walls, notification spam, and
scroll-jacking.
"""


def get_annoyance_shield_js():
    """Return JS that detects and removes web annoyances."""
    return """(function() {
    if (window.__shroudAnnoyanceShield) return;
    window.__shroudAnnoyanceShield = true;

    // ── Config ──────────────────────────────────────────────────
    var CHECK_INTERVAL = 10000;  // ms between scans
    var Z_INDEX_THRESHOLD = 9000;
    var AREA_THRESHOLD = 0.3;    // overlay must cover >30% of viewport

    // ── Known annoyance selectors ───────────────────────────────
    // Chat widgets
    var CHAT_SELECTORS = [
        '#intercom-container', '#intercom-frame', 'iframe[name="intercom-messenger-frame"]',
        '.intercom-lightweight-app',
        '#drift-widget', '#drift-frame', '#drift-widget-container',
        '[class*="crisp-client"]', '#crisp-chatbox',
        '#hubspot-messages-iframe-container',
        '#tidio-chat', '#tidio-chat-iframe',
        '.fb_dialog', '.fb-customerchat',
        '#livechat-compact-container', '#livechat-full',
        '#zsiq_float', '#zsiq_a498',  /* Zoho */
        '#launcher', /* Zendesk */
        '[class*="helpshift"]',
        '#beacon-container', /* Help Scout */
        '.gorgias-chat-container',
        '#tawk-bubble-container', '#tawkchat-container',
        '[id^="fc_frame"]', /* Freshchat */
        '.olark-launch-button', '#habla_window_div',
    ].join(',');

    // Cookie consent SDKs
    var CONSENT_SELECTORS = [
        '#onetrust-consent-sdk', '#onetrust-banner-sdk',
        '#CybotCookiebotDialog', '#CybotCookiebotDialogBodyButtonDecline',
        '.cc-window', '.cc-banner',           /* Cookie Consent */
        '#cookie-law-info-bar',
        '#gdpr-cookie-notice',
        '#cookie-notice',
        '.cookie-notice-container',
        '#cookieConsentContainer',
        '[class*="CookieConsent"]',
        '.truste_box_overlay', '#truste-consent-track',
        '#qc-cmp2-container',                  /* Quantcast */
        '.fc-consent-root',                     /* Funding Choices */
        '#sp_message_container_',               /* Sourcepoint */
        '.evidon-consent-button',
        '#usercentrics-root',
        '.iubenda-cs-container',
        '#cookies-eu-banner',
        '.js-cookie-consent',
        '#moove_gdpr_cookie_info_bar',
    ].join(',');

    // Newsletter / signup popups (common patterns)
    var NEWSLETTER_SELECTORS = [
        '[class*="newsletter-popup"]', '[class*="newsletter-modal"]',
        '[class*="signup-modal"]', '[class*="signup-popup"]',
        '[class*="subscribe-modal"]', '[class*="subscribe-popup"]',
        '[id*="newsletter-popup"]', '[id*="newsletter-modal"]',
        '[class*="email-popup"]', '[class*="email-modal"]',
        '[class*="exit-intent"]', '[class*="exitintent"]',
        '[class*="popup-overlay"]',
        '.sumo-overlay',
        '#om-popup', '[class*="OptinMonster"]',
        '.mc-modal', /* Mailchimp */
        '[class*="klaviyo-form"]',
    ].join(',');

    // Anti-adblock overlays
    var ANTI_ADBLOCK_SELECTORS = [
        '[class*="adblock-notice"]', '[class*="adblock-modal"]',
        '[class*="ad-blocker"]', '[class*="adblocker"]',
        '[id*="adblock-notice"]', '[id*="adblock-modal"]',
        '[class*="disable-adblock"]',
        '#blockadblock',
    ].join(',');

    // Floating video players
    var FLOATING_VIDEO_SELECTORS = [
        '[class*="sticky-video"]', '[class*="floating-video"]',
        '[class*="video-float"]', '[class*="pip-player"]',
        'video[style*="position: fixed"]',
    ].join(',');

    // App install banners
    var APP_BANNER_SELECTORS = [
        '[class*="app-banner"]', '[class*="smart-banner"]',
        '[class*="download-app"]', '[class*="install-app"]',
        '.smartbanner', '#smartbanner',
        '[class*="branch-banner"]',
    ].join(',');

    // ── Core removal logic ──────────────────────────────────────

    function removeBySelectors(sel) {
        try {
            var els = document.querySelectorAll(sel);
            for (var i = 0; i < els.length; i++) {
                els[i].remove();
            }
            return els.length;
        } catch(e) { return 0; }
    }

    function restoreScroll() {
        // Sites often set overflow:hidden on body/html when showing modals
        var body = document.body;
        var html = document.documentElement;
        if (body) {
            if (body.style.overflow === 'hidden') body.style.overflow = '';
            if (body.style.overflowY === 'hidden') body.style.overflowY = '';
            body.classList.remove('modal-open', 'no-scroll', 'noscroll',
                'overflow-hidden', 'is-locked', 'has-overlay');
        }
        if (html) {
            if (html.style.overflow === 'hidden') html.style.overflow = '';
            if (html.style.overflowY === 'hidden') html.style.overflowY = '';
        }
    }

    // ── Heuristic overlay detector ──────────────────────────────

    function detectAndKillOverlays() {
        var vpW = window.innerWidth;
        var vpH = window.innerHeight;
        var vpArea = vpW * vpH;
        if (vpArea === 0) return;

        // Find fixed/sticky elements with high z-index (targeted selectors)
        var candidates = document.querySelectorAll(
            '[style*="position: fixed"], [style*="position: sticky"], ' +
            '[class*="modal"], [class*="overlay"], [class*="popup"], ' +
            '[id*="modal"], [id*="overlay"], [id*="popup"], ' +
            '[role="dialog"], [role="alertdialog"]'
        );
        for (var i = 0; i < candidates.length; i++) {
            var el = candidates[i];
            var style = window.getComputedStyle(el);
            var pos = style.position;
            if (pos !== 'fixed' && pos !== 'sticky') continue;
            // Skip elements that are clearly UI (small buttons, headers under 80px)
            var rect = el.getBoundingClientRect();
            var elArea = rect.width * rect.height;
            // Skip tiny elements or narrow bars (nav bars, cookie bars under 100px tall)
            if (elArea < vpArea * AREA_THRESHOLD) continue;
            // Check z-index
            var z = parseInt(style.zIndex, 10);
            if (isNaN(z) || z < Z_INDEX_THRESHOLD) continue;
            // Check if it has a backdrop-like appearance (semi-transparent bg)
            var bg = style.backgroundColor;
            if (bg && bg.indexOf('rgba') !== -1) {
                var alpha = parseFloat(bg.split(',')[3]);
                if (alpha > 0 && alpha < 0.95) {
                    // This is likely a backdrop overlay — kill it
                    el.remove();
                    restoreScroll();
                    continue;
                }
            }
            // Also catch overlays with solid dark/light backgrounds covering the viewport
            if (elArea > vpArea * 0.7 && z >= Z_INDEX_THRESHOLD) {
                el.remove();
                restoreScroll();
            }
        }
    }

    // ── Cookie consent auto-decline ─────────────────────────────

    function autoDeclineConsent() {
        // Try clicking known "decline/reject" buttons
        var declineButtons = [
            '#onetrust-reject-all-handler',
            '#CybotCookiebotDialogBodyButtonDecline',
            '.cc-deny', '.cc-dismiss',
            '[data-action="decline"]',
            'button[class*="reject"]',
            'button[class*="decline"]',
            '.fc-cta-do-not-consent',           /* Funding Choices */
            '#sp_choice_type_11',                /* Sourcepoint reject */
            '.iubenda-cs-reject-btn',
            '#cookies-eu-reject',
            '.js-cookie-consent-decline',
            '#moove_gdpr_cookie_info_bar .moove-gdpr-infobar-reject-btn',
        ];
        for (var i = 0; i < declineButtons.length; i++) {
            try {
                var btn = document.querySelector(declineButtons[i]);
                if (btn) { btn.click(); return true; }
            } catch(e) {}
        }
        return false;
    }

    // ── Notification permission auto-deny ────────────────────────

    if (window.Notification && Notification.permission === 'default') {
        // Override Notification.requestPermission to auto-deny
        var _origNotifReq = Notification.requestPermission;
        Notification.requestPermission = function(callback) {
            if (callback) callback('denied');
            return Promise.resolve('denied');
        };
    }

    // ── Main scan function ──────────────────────────────────────

    function scan() {
        removeBySelectors(CHAT_SELECTORS);
        removeBySelectors(NEWSLETTER_SELECTORS);
        removeBySelectors(ANTI_ADBLOCK_SELECTORS);
        removeBySelectors(FLOATING_VIDEO_SELECTORS);
        removeBySelectors(APP_BANNER_SELECTORS);

        // Cookie consent: try auto-decline first, then remove if no button found
        if (!autoDeclineConsent()) {
            removeBySelectors(CONSENT_SELECTORS);
        }

        detectAndKillOverlays();
        restoreScroll();
    }

    // ── Run ─────────────────────────────────────────────────────

    // Initial scan after a brief delay (let page JS render its annoyances)
    setTimeout(scan, 800);
    setTimeout(scan, 2500);

    // Periodic re-scan for dynamically injected annoyances
    setInterval(scan, CHECK_INTERVAL);

    // Also scan on DOM changes (throttled)
    var _scanTimer = null;
    var observer = new MutationObserver(function() {
        if (_scanTimer) return;
        _scanTimer = setTimeout(function() {
            _scanTimer = null;
            scan();
        }, 500);
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});

})();"""
