"""Content blocking mixin — loading indicators, ad blocking, privacy panel."""

import json

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
)
from PyQt6.QtWebEngineCore import QWebEngineScript

from browser import storage, style, filterlists
from browser.annoyance_shield import get_annoyance_shield_js
from browser.background_activity import get_background_activity_js
from browser.fingerprint import get_fingerprint_resistance_js
from browser.pwa import detect_manifest_js
from browser.privacy_panel import PrivacyPanel
from browser.extensions import ExtensionManager


class ContentBlockingMixin:
    """Loading indicators and content blocking methods (mixin, no __init__)."""

    # ------------------------------------------------------------------
    # Loading indicators
    # ------------------------------------------------------------------

    def _load_started(self, view=None):
        self._progress.setVisible(True)
        self._progress.setValue(0)
        # Save scroll position and track previous URL before navigating away
        if view:
            url = view.url().toString()
            view._prev_url = url  # used by _load_finished to detect same-page nav
            if self._settings.get("remember_scroll_position", True):
                if url and not url.startswith("shroud:"):
                    view.page().runJavaScript(
                        "(document.documentElement.scrollTop || document.body.scrollTop) "
                        "/ Math.max(1, document.documentElement.scrollHeight - window.innerHeight)",
                        lambda pos: storage.set_scroll_position(url, pos or 0),
                    )
        # Dismiss autofill bar on navigation
        if self._autofill_bar:
            self._autofill_bar._remove()
            self._autofill_bar = None
        # Before navigating away, check if credentials were captured from a form submit
        if self._vault.is_unlocked:
            self._harvest_submitted_credentials(view)

    def _load_progress(self, progress):
        self._progress.setValue(progress)

    def _build_page_injection_js(self, view):
        """Build a single JS string combining all non-callback page injections."""
        parts = []
        # Cosmetic CSS (ad hiding + cookie banners)
        if self._cosmetic_css and self._settings.get("enable_adblock", True):
            css_js = ("var s=document.createElement('style');"
                      "s.id='shroud-cosmetic-css';"
                      "s.textContent=" + json.dumps(self._cosmetic_css) + ";"
                      "document.head.appendChild(s);")
            parts.append(css_js)
        # Dynamic cosmetic observer + script blocker
        if self._settings.get("enable_adblock", True):
            parts.append(self._get_content_blocking_js())
        # Fingerprint resistance
        if self._settings.get("fingerprint_resistance", False):
            parts.append(get_fingerprint_resistance_js())
        # Annoyance shield
        if self._settings.get("annoyance_shield", True):
            parts.append(get_annoyance_shield_js())
        # Link Intelligence hover tooltips
        if self._settings.get("link_intelligence", True):
            parts.append(self._get_link_intel_js())
        # Restore scroll position (skip if same-page nav / refresh)
        if self._settings.get("remember_scroll_position", True):
            cur_url = view.url().toString()
            prev_url = getattr(view, "_prev_url", "")
            if cur_url != prev_url:
                pos = storage.get_scroll_position(cur_url)
                if pos > 0.01:
                    parts.append(
                        f"window.scrollTo(0, {pos} * "
                        f"(document.documentElement.scrollHeight - window.innerHeight));"
                    )
        # Form draft auto-save
        if self._settings.get("form_draft_autosave", True):
            url = view.url().toString()
            draft = storage.get_form_draft(url)
            draft_json = json.dumps(draft) if draft else "null"
            parts.append(self._get_form_draft_js(draft_json))
        # PWA manifest detection
        parts.append(detect_manifest_js())
        # Background activity detection (service workers & push subscriptions)
        parts.append(get_background_activity_js())
        # Mixed content detection (HTTPS pages loading HTTP subresources)
        parts.append(
            "if (location.protocol === 'https:') {"
            "  var mixed = document.querySelectorAll("
            "    'img[src^=\"http:\"], script[src^=\"http:\"], link[href^=\"http:\"], '"
            "    + 'iframe[src^=\"http:\"], video[src^=\"http:\"], audio[src^=\"http:\"], '"
            "    + 'object[data^=\"http:\"], embed[src^=\"http:\"]'"
            "  );"
            "  if (mixed.length > 0) {"
            "    console.log('__SHROUD_MIXED_CONTENT__:' + mixed.length);"
            "  }"
            "}"
        )
        # CSP violation listener
        parts.append(
            "document.addEventListener('securitypolicyviolation', function(e) {"
            "  console.log('__SHROUD_CSP_VIOLATION__:' + JSON.stringify({"
            "    directive: e.violatedDirective,"
            "    blocked: e.blockedURI,"
            "    source: e.sourceFile"
            "  }));"
            "});"
        )
        if not parts:
            return ""
        return "(function(){" + "\n".join(parts) + "})();"

    def _load_finished(self, ok):
        self._progress.setVisible(False)
        self._update_adblock_label()
        if ok:
            view = self._current_view()
            # Apply per-site settings
            if view:
                from browser.site_settings import get_site_settings
                host = view.url().host()
                if host:
                    site_cfg = get_site_settings(host)
                    page_settings = view.page().settings()
                    from PyQt6.QtWebEngineCore import QWebEngineSettings
                    page_settings.setAttribute(
                        QWebEngineSettings.WebAttribute.JavascriptEnabled,
                        site_cfg.get("js_enabled", True),
                    )
                    page_settings.setAttribute(
                        QWebEngineSettings.WebAttribute.AutoLoadImages,
                        site_cfg.get("images_enabled", True),
                    )
                    page_settings.setAttribute(
                        QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture,
                        not site_cfg.get("media_autoplay", False),
                    )
            if view and getattr(view, '_reader_mode_active', False):
                pass  # Reader mode page — skip content injection
            elif view and not view.url().toString().startswith("shroud:"):
                # Single combined injection for all non-callback scripts
                combined_js = self._build_page_injection_js(view)
                if combined_js:
                    view.page().runJavaScript(combined_js)
                # Scriptlet injection from enhanced filter engine
                if hasattr(self._adblocker, '_engine'):
                    domain = view.url().host()
                    if domain:
                        scriptlet_js = self._adblocker._engine.get_scriptlets_for_domain(domain)
                        if scriptlet_js:
                            view.page().runJavaScript(scriptlet_js)
                # --- Callback-requiring scripts (need separate IPC calls) ---
                # Estimate reading time
                view.page().runJavaScript(
                    "(document.body&&document.body.innerText||'').split(/\\s+/).length",
                    self._update_reading_time,
                )
                # Mixed content detection (callback-based for icon update)
                if view.url().scheme() == "https":
                    view._has_mixed_content = False
                    target_view = view
                    view.page().runJavaScript(
                        "document.querySelectorAll("
                        "'img[src^=\"http:\"], script[src^=\"http:\"], "
                        "link[href^=\"http:\"], iframe[src^=\"http:\"], "
                        "video[src^=\"http:\"], audio[src^=\"http:\"], "
                        "object[data^=\"http:\"], embed[src^=\"http:\"]'"
                        ").length",
                        lambda count, v=target_view: self._on_mixed_content_detected(count, v),
                    )
                # Warn about password fields on HTTP pages
                if view.url().scheme() == "http":
                    view.page().runJavaScript(
                        "!!document.querySelector('input[type=password]')",
                        lambda has_pw: self._show_http_password_warning()
                        if has_pw else None,
                    )
            else:
                self._reading_time_label.setVisible(False)
            if self._vault.is_unlocked:
                self._check_page_for_passwords()
                self._check_session_for_credentials()
            # Give the web view keyboard focus on new-tab so typing
            # reaches the page's keydown listener immediately.
            if view and view.url().scheme() == "shroud" and view.url().host() == "newtab":
                view.setFocus()

            # WARC capture — record page if capture is active
            if hasattr(self, '_warc_capture') and self._warc_capture.is_active:
                capture_url = view.url().toString()
                capture_title = view.title() or ""
                view.page().toHtml(lambda html: self._warc_capture.add_page(
                    capture_url, capture_title, html
                ))

            # Extension content scripts
            if hasattr(self, '_extension_manager') and view and not view.url().toString().startswith("shroud:"):
                url = view.url().toString()
                ext_js, ext_css = self._extension_manager.get_scripts_for_url(url)
                if ext_css:
                    css_js = (
                        "(function(){var s=document.createElement('style');"
                        "s.textContent=" + json.dumps(ext_css) + ";"
                        "document.head.appendChild(s);})();"
                    )
                    view.page().runJavaScript(css_js)
                if ext_js:
                    view.page().runJavaScript(ext_js)

    def _install_content_blocking_script(self):
        """Install a user script that blocks ad scripts at document creation time."""
        script = QWebEngineScript()
        script.setName("shroud-script-blocker")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        script.setRunsOnSubFrames(True)
        script.setSourceCode("""(function() {
            // Override document.createElement to intercept script creation
            var origCreate = document.createElement.bind(document);
            var blockedPatterns = [
                /googlesyndication\\.com/,
                /googleadservices\\.com/,
                /pagead/,
                /adsbygoogle/,
                /doubleclick\\.net/,
                /google-analytics\\.com/,
                /googletagmanager\\.com/,
                /facebook\\.net.*fbevents/,
                /connect\\.facebook\\.net/,
                /amazon-adsystem\\.com/,
                /scorecardresearch\\.com/,
                /cdn\\.taboola\\.com/,
                /cdn\\.outbrain\\.com/
            ];
            document.createElement = function(tag) {
                var el = origCreate(tag);
                if (tag.toLowerCase() === 'script') {
                    var origSet = Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, 'src');
                    if (origSet && origSet.set) {
                        Object.defineProperty(el, 'src', {
                            get: origSet.get,
                            set: function(val) {
                                for (var i = 0; i < blockedPatterns.length; i++) {
                                    if (blockedPatterns[i].test(val)) {
                                        return;
                                    }
                                }
                                origSet.set.call(this, val);
                            },
                            configurable: true
                        });
                    }
                }
                return el;
            };
        })();""")
        self._profile.scripts().insert(script)

    def _get_content_blocking_js(self):
        """Return JS that dynamically hides ad elements and blocks ad scripts."""
        return """(function() {
            if (window.__shroudContentBlock) return;
            window.__shroudContentBlock = true;

            // Blocked script URL patterns
            var blockedScriptPatterns = [
                /googlesyndication\\.com/,
                /googleadservices\\.com/,
                /pagead/,
                /adsbygoogle/,
                /doubleclick\\.net/,
                /google-analytics\\.com/,
                /googletagmanager\\.com/,
                /facebook\\.net.*fbevents/,
                /connect\\.facebook\\.net/,
                /ads\\.linkedin\\.com/,
                /analytics\\.tiktok\\.com/,
                /cdn\\.taboola\\.com/,
                /cdn\\.outbrain\\.com/,
                /scorecardresearch\\.com/,
                /amazon-adsystem\\.com/
            ];

            function isBlockedScript(src) {
                if (!src) return false;
                for (var i = 0; i < blockedScriptPatterns.length; i++) {
                    if (blockedScriptPatterns[i].test(src)) return true;
                }
                return false;
            }

            // Hide ad-like elements dynamically
            var adSelectors = [
                '.ad', '.ads', '.adsbygoogle', 'ins.adsbygoogle',
                '[id^="google_ads"]', '[id^="div-gpt-ad"]',
                '[class*="ad-slot"]', '[class*="ad-unit"]',
                '[id*="ad-slot"]', '[id*="ad-unit"]',
                '.ad-banner', '.ad-container', '.ad-wrapper',
                '.advertisement', '.sponsored'
            ].join(',');

            function hideAdElements(root) {
                try {
                    var els = (root || document).querySelectorAll(adSelectors);
                    for (var i = 0; i < els.length; i++) {
                        els[i].style.setProperty('display', 'none', 'important');
                    }
                } catch(e) {}
            }

            // Initial pass
            hideAdElements();

            // Observe DOM for dynamically added ads and scripts (throttled)
            var _lastHide = 0;
            var _hideScheduled = false;
            var observer = new MutationObserver(function(mutations) {
                var needsHide = false;
                for (var i = 0; i < mutations.length; i++) {
                    var added = mutations[i].addedNodes;
                    for (var j = 0; j < added.length; j++) {
                        var node = added[j];
                        if (node.nodeType !== 1) continue;
                        // Block ad scripts
                        if (node.tagName === 'SCRIPT' && isBlockedScript(node.src)) {
                            node.type = 'text/blocked';
                            node.remove();
                            continue;
                        }
                        needsHide = true;
                    }
                }
                if (needsHide) {
                    var now = Date.now();
                    if (now - _lastHide > 150) {
                        _lastHide = now;
                        hideAdElements();
                    } else if (!_hideScheduled) {
                        _hideScheduled = true;
                        requestAnimationFrame(function() { _hideScheduled = false; _lastHide = Date.now(); hideAdElements(); });
                    }
                }
            });
            observer.observe(document.documentElement, {childList: true, subtree: true});
        })();"""

    def _hard_reload(self):
        """Reload bypassing cache."""
        view = self._current_view()
        if view:
            view.triggerPageAction(view.page().WebAction.ReloadAndBypassCache)

    def _show_http_password_warning(self):
        """Show a warning bar when a password field is found on an HTTP page."""
        # Don't show if there's already one
        if hasattr(self, '_http_pw_bar') and self._http_pw_bar:
            return
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background: {style.BG_CARD}; "
            f"border-bottom: 2px solid {style.RED}; "
            f"padding: 6px 14px; }}"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(10)
        label = QLabel(
            "\u26A0 This page has a login form but is not using HTTPS. "
            "Your password could be intercepted."
        )
        label.setStyleSheet(f"color: {style.RED}; font-size: 13px;")
        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        dismiss_btn.setFixedHeight(28)
        dismiss_btn.clicked.connect(lambda: (
            bar.setParent(None), bar.deleteLater(),
            setattr(self, '_http_pw_bar', None),
        ))
        h.addWidget(label)
        h.addStretch()
        h.addWidget(dismiss_btn)
        self._central_layout.insertWidget(0, bar)
        self._http_pw_bar = bar

    def _on_mixed_content_detected(self, count, view):
        """Flag the view when mixed HTTP content is found on an HTTPS page."""
        if count and count > 0:
            view._has_mixed_content = True
            # Update the security icon if this is still the active view
            if view is self._current_view():
                self._update_security_icon(view.url())

    def _update_reading_time(self, word_count):
        """Update the reading time estimate in the status bar."""
        if not word_count or word_count < 100:
            self._reading_time_label.setVisible(False)
            return
        minutes = max(1, round(word_count / 238))
        if minutes < 60:
            self._reading_time_label.setText(f"  ~{minutes} min read")
        else:
            h = minutes // 60
            m = minutes % 60
            self._reading_time_label.setText(f"  ~{h}h {m}m read")
        self._reading_time_label.setVisible(True)

    def _update_adblock_label(self):
        if self._adblocker.enabled:
            count = self._adblocker.blocked_count
            self._adblock_label.setText(f"  {count} blocked")
            self._adblock_label.setStyleSheet(style.ADBLOCK_LABEL_ON_STYLE)
        else:
            self._adblock_label.setText("  shield off")
            self._adblock_label.setStyleSheet(style.ADBLOCK_LABEL_OFF_STYLE)

    def _show_privacy_panel(self):
        """Open the Privacy Dashboard for the current tab."""
        panel = PrivacyPanel(self, parent=self)
        panel.exec()

    def _handle_privacy_action(self, data):
        """Process an action from the shroud://privacy page."""
        action = data.get("action", "")
        arg1 = data.get("arg1", "")
        arg2 = data.get("arg2", "")

        if action == "allow" and arg1 and arg2:
            storage.set_site_exception(arg1, arg2, "allow")
            self._adblocker.set_site_exceptions(storage.load_site_exceptions())
        elif action == "block" and arg1 and arg2:
            storage.set_site_exception(arg1, arg2, "block")
            self._adblocker.set_site_exceptions(storage.load_site_exceptions())
        elif action == "undo_exc" and arg1 and arg2:
            storage.remove_site_exception(arg1, arg2)
            self._adblocker.set_site_exceptions(storage.load_site_exceptions())
        elif action == "del_cookies" and arg1:
            self._delete_cookies_for_domain(arg1)
        elif action == "revoke" and arg1 and arg2:
            storage.remove_permission(arg1, arg2)
