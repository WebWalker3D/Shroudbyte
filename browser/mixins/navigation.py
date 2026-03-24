from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QStandardItem, QStandardItemModel

from browser import __app_name__, storage, style
from browser.reader import READER_EXTRACT_JS, generate_reader_html


class NavigationMixin:
    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate_to_url(self):
        text = self._url_bar.text().strip()
        if not text:
            return

        # Treat as a URL if it already has a scheme, contains a dot, or
        # looks like a localhost/IP address (with optional port).
        has_scheme = text.startswith(("http://", "https://", "file://", "shroud://"))
        looks_like_url = (
            has_scheme
            or ("." in text and " " not in text)
            or text.startswith("localhost")
            or text.startswith("127.0.0.1")
            or text.startswith("[::1]")
        )

        if looks_like_url:
            if not has_scheme:
                scheme = "https://" if "." in text else "http://"
                text = scheme + text
            url = QUrl(text)
        else:
            search = self._settings.get(
                "search_engine", "https://duckduckgo.com/?q={}"
            )
            url = QUrl(search.format(QUrl.toPercentEncoding(text).data().decode()))

        self._current_view().load(url)

    def _go_home(self):
        view = self._current_view()
        if view:
            view.load(QUrl("shroud://newtab"))
        else:
            self.add_new_tab()

    # ------------------------------------------------------------------
    # Reader mode
    # ------------------------------------------------------------------

    def _toggle_reader_mode(self):
        view = self._current_view()
        if not view:
            return
        url = view.url().toString()
        if url.startswith("shroud:"):
            return

        if getattr(view, '_reader_mode_active', False):
            # Exit reader mode — reload original page
            view._reader_mode_active = False
            original_url = getattr(view, '_reader_mode_url', url)
            view.load(QUrl(original_url))
            self._update_reader_btn()
        else:
            # Enter reader mode — extract article content
            view._reader_mode_url = url
            target_view = view
            view.page().runJavaScript(
                READER_EXTRACT_JS,
                lambda result, v=target_view: self._on_reader_extract(result, v),
            )

    def _on_reader_extract(self, result, target_view):
        view = self._current_view()
        if view is not target_view:
            return
        if not result or not isinstance(result, dict) or not result.get('content'):
            self._status.showMessage("Could not extract article content", 3000)
            return

        original_url = getattr(view, '_reader_mode_url', view.url().toString())
        reader_html = generate_reader_html(
            title=result.get('title', ''),
            byline=result.get('byline', ''),
            content=result.get('content', ''),
            site_name=result.get('siteName', ''),
            original_url=original_url,
        )
        view._reader_mode_active = True
        view.page().setHtml(reader_html, QUrl(original_url))
        self._update_reader_btn()

    def _update_reader_btn(self):
        view = self._current_view()
        if view and getattr(view, '_reader_mode_active', False):
            self._reader_btn.setStyleSheet(style.READER_BTN_ACTIVE_STYLE)
        else:
            self._reader_btn.setStyleSheet(style.NAV_BTN_STYLE)

    def _update_url_bar(self, url):
        if url.scheme() == "shroud" and url.host() == "newtab":
            self._url_bar.setText("")
        else:
            self._url_bar.setText(url.toString())
            self._url_bar.setCursorPosition(0)
        self._update_security_icon(url)

    def _update_security_icon(self, url):
        scheme = url.scheme()
        view = self._current_view()
        has_mixed = view and getattr(view, '_has_mixed_content', False)
        if scheme == "https" and has_mixed:
            self._security_icon.setText("\u26a0")
            self._security_icon.setToolTip(
                "Secure connection (HTTPS) — mixed content detected"
            )
            self._security_icon.setStyleSheet(
                f"color: {style.YELLOW}; font-size: 14px; padding: 0;"
            )
        elif scheme == "https":
            self._security_icon.setText("\U0001f512")
            self._security_icon.setToolTip("Secure connection (HTTPS)")
            self._security_icon.setStyleSheet(
                f"color: {style.GREEN}; font-size: 14px; padding: 0;"
            )
        elif scheme == "http":
            self._security_icon.setText("\u26a0")
            self._security_icon.setToolTip("Not secure (HTTP)")
            self._security_icon.setStyleSheet(
                f"color: {style.YELLOW}; font-size: 14px; padding: 0;"
            )
        elif scheme == "shroud":
            self._security_icon.setText("\U0001f6e1")
            self._security_icon.setToolTip("Internal page")
            self._security_icon.setStyleSheet(
                f"color: {style.ACCENT}; font-size: 14px; padding: 0;"
            )
        elif scheme == "file":
            self._security_icon.setText("\U0001f4c1")
            self._security_icon.setToolTip("Local file")
            self._security_icon.setStyleSheet(
                f"color: {style.TEXT_DIM}; font-size: 14px; padding: 0;"
            )
        else:
            self._security_icon.setText("")
            self._security_icon.setToolTip("")

    def _show_site_controls(self):
        """Show per-site control popup when security icon is clicked."""
        view = self._current_view()
        if not view:
            return
        host = view.url().host()
        if not host:
            return

        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QCheckBox, QLabel, QPushButton,
            QComboBox, QFormLayout,
        )
        from browser.site_settings import get_site_settings, set_site_setting
        from browser import style

        cfg = get_site_settings(host)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Site Controls \u2014 {host}")
        dialog.setMinimumWidth(350)
        dialog.setStyleSheet(style.SETTINGS_FORM_STYLE)

        layout = QFormLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel(f"Settings for {host}")
        header.setStyleSheet(f"color: {style.TEXT}; font-size: 14px; font-weight: bold;")
        layout.addRow(header)

        js_check = QCheckBox("Enabled")
        js_check.setChecked(cfg.get("js_enabled", True))
        layout.addRow("JavaScript", js_check)

        cookies_check = QCheckBox("Enabled")
        cookies_check.setChecked(cfg.get("cookies_enabled", True))
        layout.addRow("Cookies", cookies_check)

        images_check = QCheckBox("Enabled")
        images_check.setChecked(cfg.get("images_enabled", True))
        layout.addRow("Images", images_check)

        autoplay_check = QCheckBox("Enabled")
        autoplay_check.setChecked(cfg.get("media_autoplay", False))
        layout.addRow("Media Autoplay", autoplay_check)

        fp_check = QCheckBox("Enabled")
        fp_check.setChecked(cfg.get("fingerprint_resistance", False))
        layout.addRow("Fingerprint Resistance", fp_check)

        referrer_combo = QComboBox()
        referrer_options = ["default", "no-referrer", "origin"]
        referrer_combo.addItems(referrer_options)
        current_ref = cfg.get("referrer_policy", "default")
        if current_ref in referrer_options:
            referrer_combo.setCurrentIndex(referrer_options.index(current_ref))
        layout.addRow("Referrer Policy", referrer_combo)

        webrtc_combo = QComboBox()
        webrtc_options = ["default", "disable_non_proxied_udp"]
        webrtc_combo.addItems(webrtc_options)
        current_rtc = cfg.get("webrtc_policy", "default")
        if current_rtc in webrtc_options:
            webrtc_combo.setCurrentIndex(webrtc_options.index(current_rtc))
        layout.addRow("WebRTC Policy", webrtc_combo)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        layout.addRow(save_btn)

        def save():
            set_site_setting(host, "js_enabled", js_check.isChecked())
            set_site_setting(host, "cookies_enabled", cookies_check.isChecked())
            set_site_setting(host, "images_enabled", images_check.isChecked())
            set_site_setting(host, "media_autoplay", autoplay_check.isChecked())
            set_site_setting(host, "fingerprint_resistance", fp_check.isChecked())
            set_site_setting(host, "referrer_policy", referrer_combo.currentText())
            set_site_setting(host, "webrtc_policy", webrtc_combo.currentText())
            dialog.accept()
            # Reload to apply
            view.reload()

        save_btn.clicked.connect(save)
        dialog.exec()

    def _update_title(self, title):
        suffix = "  [Private]" if self._private_mode else ""
        self.setWindowTitle(f"{title} — {__app_name__}{suffix}")

    def _focus_url_bar(self):
        self._url_bar.setFocus()
        self._url_bar.selectAll()

    # ------------------------------------------------------------------
    # URL autocomplete helpers
    # ------------------------------------------------------------------

    # Custom data role for "Switch to tab" indicator
    TAB_SWITCH_ROLE = Qt.ItemDataRole.UserRole + 2
    # Custom data role for search suggestion indicator
    SEARCH_SUGGESTION_ROLE = Qt.ItemDataRole.UserRole + 3

    def _refresh_suggestions(self):
        """Reload the completer model from history + bookmarks."""
        suggestions = storage.get_url_suggestions()
        self._completer_model.blockSignals(True)
        self._completer_model.clear()
        for url, title, _freq in suggestions:
            item = QStandardItem(url)
            item.setData(title, Qt.ItemDataRole.UserRole + 1)
            self._completer_model.appendRow(item)
        self._completer_model.blockSignals(False)
        self._completer_proxy.invalidate()

    def _filter_completions(self, text):
        """Update the proxy filter as the user types (debounced)."""
        # Don't re-filter while the user is arrowing through the popup —
        # Qt updates the line edit text as items are highlighted, which
        # would reset the model and snap the selection back to row 0.
        # But if the text no longer matches the highlighted item, the user
        # actually typed or deleted — allow the filter to run.
        popup = self._url_completer.popup()
        if popup.isVisible() and popup.currentIndex().isValid():
            highlighted = popup.currentIndex().data(Qt.ItemDataRole.DisplayRole)
            if highlighted == text:
                return
        if not hasattr(self, '_filter_timer'):
            self._filter_timer = QTimer(self)
            self._filter_timer.setSingleShot(True)
            self._filter_timer.timeout.connect(self._apply_filter)
        self._pending_filter_text = text
        self._filter_timer.start(120)

    def _apply_filter(self):
        """Apply the debounced filter text to the proxy model."""
        text = self._pending_filter_text
        self._completer_proxy.setFilterFixedString(text)

        # Inject open-tab matches into the model
        self._inject_tab_matches(text)

        # Trigger live search suggestions for queries >= 3 chars (opt-in)
        if len(text) >= 3 and self._settings.get("search_suggestions", False):
            if not hasattr(self, '_search_suggest_timer'):
                self._search_suggest_timer = QTimer(self)
                self._search_suggest_timer.setSingleShot(True)
                self._search_suggest_timer.timeout.connect(self._do_fetch_search_suggestions)
            self._pending_suggest_text = text
            self._search_suggest_timer.start(300)

    def _get_open_tab_matches(self, text):
        """Search open tab titles and URLs for matches. Returns list of (index, title, url)."""
        if not text:
            return []
        query = text.lower()
        matches = []
        for i in range(self._tabs.count()):
            view = self._tabs.widget(i)
            if view and view is not self._current_view():
                tab_url = view.url().toString()
                tab_title = view.title() or self._tabs.tabText(i)
                if query in tab_url.lower() or query in tab_title.lower():
                    matches.append((i, tab_title, tab_url))
        return matches

    def _inject_tab_matches(self, text):
        """Add open-tab matches to the completer model."""
        # Remove any previous tab-switch items
        model = self._completer_model
        rows_to_remove = []
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            if model.data(idx, self.TAB_SWITCH_ROLE):
                rows_to_remove.append(row)
        for row in reversed(rows_to_remove):
            model.removeRow(row)

        # Add matching open tabs
        tab_matches = self._get_open_tab_matches(text)
        for tab_index, title, url in tab_matches[:5]:
            display = url
            item = QStandardItem(display)
            item.setData(f"Switch to tab: {title}", Qt.ItemDataRole.UserRole + 1)
            item.setData(tab_index, self.TAB_SWITCH_ROLE)
            model.appendRow(item)

        if tab_matches:
            self._completer_proxy.invalidate()

    def _do_fetch_search_suggestions(self):
        """Kick off a background fetch for search suggestions."""
        text = getattr(self, '_pending_suggest_text', '')
        if len(text) < 3:
            return
        self._fetch_search_suggestions(text)

    def _fetch_search_suggestions(self, text):
        """Fetch search suggestions from DuckDuckGo in a background thread."""
        import threading
        import urllib.request
        import urllib.parse
        import json

        query = text

        def _worker():
            try:
                encoded = urllib.parse.quote(query)
                url = f"https://duckduckgo.com/ac/?q={encoded}&type=list"
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "Mozilla/5.0")
                resp = urllib.request.urlopen(req, timeout=3)
                data = json.loads(resp.read().decode("utf-8"))
                # DuckDuckGo returns [query, [suggestions...]]
                if isinstance(data, list) and len(data) >= 2:
                    suggestions = data[1][:6]
                else:
                    suggestions = []
            except Exception:
                suggestions = []

            if suggestions:
                QTimer.singleShot(0, lambda: self._merge_search_suggestions(query, suggestions))

        threading.Thread(target=_worker, daemon=True).start()

    def _merge_search_suggestions(self, query, suggestions):
        """Merge web search suggestions into the completer model (GUI thread)."""
        # Only merge if the user hasn't changed the query
        current = getattr(self, '_pending_filter_text', '')
        if current != query:
            return

        model = self._completer_model
        # Remove previous search suggestions
        rows_to_remove = []
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            if model.data(idx, self.SEARCH_SUGGESTION_ROLE):
                rows_to_remove.append(row)
        for row in reversed(rows_to_remove):
            model.removeRow(row)

        # Add new suggestions
        search_template = self._settings.get(
            "search_engine", "https://duckduckgo.com/?q={}"
        )
        for suggestion in suggestions:
            search_url = search_template.format(
                QUrl.toPercentEncoding(suggestion).data().decode()
            )
            item = QStandardItem(search_url)
            item.setData(f"Search: {suggestion}", Qt.ItemDataRole.UserRole + 1)
            item.setData(True, self.SEARCH_SUGGESTION_ROLE)
            model.appendRow(item)

        self._completer_proxy.invalidate()

    def _on_completion_activated(self, index):
        """Navigate to the URL chosen from the popup, or switch to a tab."""
        # Check if this is a tab-switch item
        tab_index = index.data(self.TAB_SWITCH_ROLE)
        if tab_index is not None and isinstance(tab_index, int):
            self._url_bar.clearFocus()
            self._tabs.setCurrentIndex(tab_index)
            return

        url = index.data(Qt.ItemDataRole.DisplayRole)
        if url:
            self._url_bar.setText(url)
            self._current_view().load(QUrl(url))
