import json

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QColor, QPalette

from browser import storage
from browser import style


class SettingsMixin:
    """Settings dialog helpers — mixed into BrowserWindow."""

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def _show_settings(self):
        """Open settings in a browser tab."""
        view = self._current_view()
        if view:
            view.load(QUrl("shroud://settings"))
        else:
            self.add_new_tab(QUrl("shroud://settings"))

    def _handle_settings_action(self, data, view=None):
        """Process actions from the shroud://settings page."""
        action = data.get("action", "")

        if action == "save":
            s = data.get("settings", {})
            for key in (
                "dark_mode", "wallpaper",
                "search_engine", "enable_javascript", "enable_adblock",
                "default_zoom", "user_agent", "https_only", "do_not_track",
                "restore_session", "strip_tracking", "fingerprint_resistance",
                "link_intelligence", "page_watch_interval", "auto_delete_cookies",
                "form_draft_autosave", "annoyance_shield",
                "remember_scroll_position", "screen_time_tracking",
                "clipboard_history",
                "search_suggestions",
                "dns_over_https", "dns_over_https_provider", "custom_dns_fallback",
                "vault_auto_lock_minutes",
                "spellcheck_enabled", "permission_ttl_days",
                "tab_hibernate_minutes",
                "check_for_updates",
            ):
                if key in s:
                    self._settings[key] = s[key]

            storage.save_settings(self._settings)
            self._apply_settings_runtime()
            self._status.showMessage("Settings saved", 2000)
            return

        if action == "register":
            server_url = data.get("server_url", "").strip()
            if not server_url:
                self._settings_page_result(view, error="Enter a server URL first.")
                return
            base = server_url.rstrip("/")
            for suffix in ("/shroud-dns-query", "/shroud-dns-register", "/health"):
                if base.endswith(suffix):
                    base = base[:-len(suffix)]
                    break
            import threading
            from PyQt6.QtCore import QTimer

            def _worker():
                try:
                    import http.client, ssl as _ssl, urllib.parse
                    parsed = urllib.parse.urlparse(base)
                    ctx = _ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = _ssl.CERT_NONE
                    conn = http.client.HTTPSConnection(
                        parsed.hostname, parsed.port or 443, context=ctx, timeout=10)
                    conn.connect()
                    conn.request("GET", "/shroud-dns-register")
                    resp = conn.getresponse()
                    if resp.status != 200:
                        raise RuntimeError(f"Server returned HTTP {resp.status}")
                    reg_data = json.loads(resp.read())
                    conn.close()
                    QTimer.singleShot(0, lambda: self._apply_dns_registration(
                        base, reg_data))
                except Exception as exc:
                    msg = str(exc)
                    QTimer.singleShot(0, lambda: self._settings_page_result(
                        view, error=f"Registration failed: {msg}"))

            threading.Thread(target=_worker, daemon=True).start()
            return

        if action == "unregister":
            storage.clear_dns_secrets(self._settings)
            self._settings["custom_dns_enabled"] = False
            self._settings["custom_dns_server"] = ""
            storage.save_settings(self._settings)
            self._restart_browser()
            return

    def _apply_dns_registration(self, base, reg_data):
        """Apply DNS registration results on the GUI thread."""
        secret = reg_data["secret"]
        fingerprint = reg_data.get("cert_fingerprint", "")
        storage.save_dns_secrets(self._settings, secret, fingerprint)
        self._settings["custom_dns_enabled"] = True
        self._settings["custom_dns_server"] = base
        storage.save_settings(self._settings)
        self._restart_browser()

    def _settings_page_result(self, view, msg=None, error=None):
        """Send a result message back to the settings page."""
        if not view or not view.page():
            return
        result = {}
        if msg:
            result["msg"] = msg
        if error:
            result["error"] = error
        view.page().runJavaScript(
            f"window.__shroudSettingsResult&&window.__shroudSettingsResult({json.dumps(result)})"
        )

    def _apply_theme(self):
        """Switch the UI between dark and light mode."""
        dark = self._settings.get("dark_mode", True)
        style.set_dark_mode(dark)

        # Qt widget stylesheets
        self.setStyleSheet(style.GLOBAL_STYLESHEET)

        # QPalette for native dialogs / fallback widgets
        from PyQt6.QtWidgets import QApplication
        qapp = QApplication.instance()
        if qapp:
            palette = QPalette()
            if dark:
                palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
                palette.setColor(QPalette.ColorRole.WindowText, QColor(238, 238, 238))
                palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
                palette.setColor(QPalette.ColorRole.AlternateBase, QColor(43, 43, 43))
                palette.setColor(QPalette.ColorRole.Text, QColor(238, 238, 238))
                palette.setColor(QPalette.ColorRole.Button, QColor(43, 43, 43))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor(238, 238, 238))
            else:
                palette.setColor(QPalette.ColorRole.Window, QColor(240, 238, 235))
                palette.setColor(QPalette.ColorRole.WindowText, QColor(44, 37, 32))
                palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
                palette.setColor(QPalette.ColorRole.AlternateBase, QColor(247, 245, 242))
                palette.setColor(QPalette.ColorRole.Text, QColor(44, 37, 32))
                palette.setColor(QPalette.ColorRole.Button, QColor(247, 245, 242))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor(44, 37, 32))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(41, 121, 255))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Link, QColor(41, 121, 255))
            qapp.setPalette(palette)

        # Re-apply component styles to toolbar widgets
        self._apply_widget_styles()

        # Reload any open shroud:// pages so they pick up new colours
        for i in range(self._tabs.count()):
            v = self._tabs.widget(i)
            if v and v.url().scheme() == "shroud":
                v.reload()

    def _apply_widget_styles(self):
        """Re-apply component stylesheets to toolbar widgets after theme change."""
        for btn in (self._back_btn, self._forward_btn, self._reload_btn,
                    self._home_btn):
            btn.setStyleSheet(style.NAV_BTN_STYLE)
        self._security_icon.setStyleSheet(
            f"color: {style.TEXT_FAINT}; font-size: 14px; padding: 0;")
        self._url_bar.setStyleSheet(style.URL_BAR_STYLE)
        self._bookmark_btn.setStyleSheet(style.BOOKMARK_BTN_STYLE)
        self._new_tab_btn.setStyleSheet(style.NEW_TAB_BTN_STYLE)

    def _apply_settings_runtime(self):
        """Apply saved settings to running browser state."""
        # Theme
        self._apply_theme()

        # Update DNS proxy if running
        if self._dns_proxy is not None:
            _base = self._settings["custom_dns_server"].rstrip("/")
            secret = storage.get_dns_secret(self._settings)
            fingerprint = storage.get_dns_cert_fingerprint(self._settings)
            self._dns_proxy.update_config(
                pfsense_url=_base + "/shroud-dns-query" if _base else "",
                shared_secret=secret,
                fallback=self._settings["custom_dns_fallback"],
                cert_fingerprint=fingerprint,
            )

        self._apply_profile_settings()
        self._adblocker.enabled = self._settings["enable_adblock"]
        self._adblocker.strip_tracking = self._settings["strip_tracking"]
        self._update_adblock_label()

        # Apply HTTPS-only to all open tabs
        for i in range(self._tabs.count()):
            v = self._tabs.widget(i)
            if v and hasattr(v.page(), "https_only"):
                v.page().https_only = self._settings["https_only"]

        self._adblocker.do_not_track = self._settings["do_not_track"]
        self._screen_time.set_enabled(self._settings.get("screen_time_tracking", False))
        self._clipboard_history.set_enabled(
            self._settings.get("clipboard_history", True) and not self._private_mode
        )
