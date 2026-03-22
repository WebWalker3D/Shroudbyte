"""Custom WebEngineView and WebEnginePage with context menus, HTTPS-only, and popup support."""

import json
import ssl
import urllib.request

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineContextMenuRequest,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QVBoxLayout

_CRED_ALERT_PREFIX = "__SHROUD_CRED_CAPTURE__:"
_PW_FOUND_ALERT = "__SHROUD_PW_FIELDS_FOUND__"
_LINK_HOVER_PREFIX = "__SHROUD_LINK_HOVER__:"
_PRIVACY_ACTION_PREFIX = "__SHROUD_PRIVACY__:"
_WATCH_ACTION_PREFIX = "__SHROUD_WATCH__:"
_SETTINGS_ACTION_PREFIX = "__SHROUD_SETTINGS__:"
_PAGE_ACT_PREFIX = "__SHROUD_PAGE_ACT__:"

# Shared set of hosts known NOT to require HTTP auth.
# Populated on successful HEAD checks; avoids repeat probes.
# Thread-safe: Python's GIL protects set.add() and `in` checks,
# but we use a dedicated lock for correctness across Qt threads.
import threading
_safe_hosts: set[str] = set()
_safe_hosts_lock = threading.Lock()


class ShroudPage(QWebEnginePage):
    """Custom page that handles new-window requests and HTTPS-only mode."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._view_ref = None
        self.https_only = False
        self._pending_creds = None
        self.featurePermissionRequested.connect(self._on_permission_requested)

    def javaScriptAlert(self, securityOrigin, msg):
        """Intercept credential-capture and password-field alerts from injected hooks."""
        if msg.startswith(_CRED_ALERT_PREFIX):
            try:
                self._pending_creds = json.loads(msg[len(_CRED_ALERT_PREFIX):])
                mw = self._get_main_window()
                if mw:
                    from PyQt6.QtCore import QTimer
                    view = self._view_ref
                    QTimer.singleShot(2000, lambda: mw._harvest_pending_creds(view))
            except Exception:
                pass
            return
        if msg == _PW_FOUND_ALERT:
            mw = self._get_main_window()
            if mw:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: mw._on_dynamic_password_fields_found())
            return
        super().javaScriptAlert(securityOrigin, msg)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Intercept link-hover messages from injected Link Intelligence JS."""
        if message.startswith(_LINK_HOVER_PREFIX):
            try:
                import json as _json
                data = _json.loads(message[len(_LINK_HOVER_PREFIX):])
                href = data.get("href", "")
                if href:
                    mw = self._get_main_window()
                    if mw and hasattr(mw, "_handle_link_hover"):
                        mw._handle_link_hover(href, self._view_ref)
            except Exception:
                pass
            return
        if message.startswith(_PRIVACY_ACTION_PREFIX):
            try:
                import json as _json
                data = _json.loads(message[len(_PRIVACY_ACTION_PREFIX):])
                mw = self._get_main_window()
                if mw and hasattr(mw, "_handle_privacy_action"):
                    mw._handle_privacy_action(data)
            except Exception:
                pass
            return
        if message.startswith(_WATCH_ACTION_PREFIX):
            try:
                import json as _json
                data = _json.loads(message[len(_WATCH_ACTION_PREFIX):])
                mw = self._get_main_window()
                if mw and hasattr(mw, "_handle_watch_action"):
                    mw._handle_watch_action(data)
            except Exception:
                pass
            return
        if message.startswith(_SETTINGS_ACTION_PREFIX):
            try:
                import json as _json
                data = _json.loads(message[len(_SETTINGS_ACTION_PREFIX):])
                mw = self._get_main_window()
                if mw and hasattr(mw, "_handle_settings_action"):
                    mw._handle_settings_action(data, self._view_ref)
            except Exception:
                pass
            return
        if message.startswith(_PAGE_ACT_PREFIX):
            try:
                import json as _json
                data = _json.loads(message[len(_PAGE_ACT_PREFIX):])
                mw = self._get_main_window()
                if mw and hasattr(mw, "_handle_page_action"):
                    mw._handle_page_action(data)
            except Exception:
                pass
            return
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)

    def createWindow(self, window_type):
        view = self._view_ref
        if view and hasattr(view, "create_window_requested"):
            new_view = view.create_window_requested()
            if new_view is not None:
                return new_view.page()
        return None

    # Loopback IPs that Chromium blocks when a SOCKS proxy is active.
    # Rewrite them to "localhost" which Chromium allows through.
    _LOOPBACK_IPS = {"127.0.0.1", "::1", "[::1]"}

    def _probe_for_auth(self, url_string):
        """Quick HEAD request to detect 401 before Chromium sees it.

        Returns True if the server requires HTTP authentication.
        Returns False for any other response (200, 404, timeout, etc.).
        """
        try:
            req = urllib.request.Request(url_string, method="HEAD")
            ctx = ssl.create_default_context()
            urllib.request.urlopen(req, timeout=1.5, context=ctx)
            return False
        except urllib.error.HTTPError as e:
            return e.code == 401
        except Exception:
            return False

    def _get_main_window(self):
        """Walk up to the MainWindow via the view reference."""
        view = self._view_ref
        if view and hasattr(view, "_tab_widget"):
            return view._tab_widget
        return None

    def _on_permission_requested(self, origin, feature):
        """Handle permission requests from web pages."""
        from . import storage

        host = origin.host()

        feature_names = {
            QWebEnginePage.Feature.Geolocation: "geolocation",
            QWebEnginePage.Feature.MediaAudioCapture: "microphone",
            QWebEnginePage.Feature.MediaVideoCapture: "camera",
            QWebEnginePage.Feature.MediaAudioVideoCapture: "camera_microphone",
            QWebEnginePage.Feature.Notifications: "notifications",
            QWebEnginePage.Feature.DesktopVideoCapture: "screen_share",
            QWebEnginePage.Feature.DesktopAudioVideoCapture: "screen_share_audio",
        }
        feature_name = feature_names.get(feature, str(feature))

        saved = storage.get_permission(host, feature_name)
        if saved == "allow":
            self.setFeaturePermission(origin, feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
            return
        elif saved == "deny":
            self.setFeaturePermission(origin, feature,
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
            return

        mw = self._get_main_window()
        if mw:
            mw._show_permission_prompt(origin, feature, feature_name, host)
        else:
            self.setFeaturePermission(origin, feature,
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        """Rewrite loopback IPs to localhost and upgrade http to https."""
        from PyQt6.QtCore import QTimer

        host = url.host()

        # Chromium blocks raw loopback IPs through a proxy — rewrite to
        # "localhost" which is excluded from proxy and resolves the same.
        if is_main_frame and host in self._LOOPBACK_IPS:
            rewritten = QUrl(url)
            rewritten.setHost("localhost")
            QTimer.singleShot(0, lambda u=rewritten: self.setUrl(u))
            return False

        # Chromium's shroud:// renderer process lacks SOCKS proxy access.
        # Allow URL bar / view.load() (NavigationTypeTyped) through.
        # For everything else (link clicks, JS), open in a fresh tab.
        if (is_main_frame
                and self.url().scheme() == "shroud"
                and url.scheme() in ("http", "https")
                and nav_type != QWebEnginePage.NavigationType.NavigationTypeTyped):
            mw = self._get_main_window()
            if mw:
                view_ref = self._view_ref
                target = QUrl(url)
                def _open():
                    mw.add_new_tab(target)
                    idx = mw._tabs.indexOf(view_ref)
                    if idx >= 0:
                        mw._close_tab(idx)
                QTimer.singleShot(0, _open)
            return False

        # ── HTTP 401 pre-check ──────────────────────────────────────
        # Chromium 134 (Qt 6.10) crashes with SIGTRAP on 401 responses.
        # Probe with a HEAD request from Python before letting Chromium
        # make the request.  If 401, block navigation and prompt for
        # credentials; the interceptor will inject the Authorization
        # header on the retry so Chromium never sees a 401.
        if is_main_frame and url.scheme() in ("http", "https"):
            host_lower = (host or "").lower()
            mw = self._get_main_window()
            has_auth = (mw and hasattr(mw, "_adblocker")
                        and host_lower in mw._adblocker._http_auth)
            with _safe_hosts_lock:
                already_safe = host_lower in _safe_hosts
            if not already_safe and not has_auth:
                if self._probe_for_auth(url.toString()):
                    if mw:
                        QTimer.singleShot(
                            0, lambda u=QUrl(url): mw._prompt_http_auth(u))
                    return False
                with _safe_hosts_lock:
                    _safe_hosts.add(host_lower)

        if self.https_only and url.scheme() == "http" and is_main_frame:
            # Don't upgrade localhost / local network
            if host not in ("localhost", "127.0.0.1", "::1") and not host.endswith(".local"):
                secure = QUrl(url)
                secure.setScheme("https")
                self.setUrl(secure)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class ShroudWebView(QWebEngineView):
    """WebEngineView subclass with tab integration and context menus."""

    def __init__(self, profile, tab_widget=None, parent=None):
        super().__init__(parent)
        self._tab_widget = tab_widget
        page = ShroudPage(profile, self)
        page._view_ref = self
        self.setPage(page)

    def create_window_requested(self):
        """Called when the page wants to open a new window/tab."""
        if self._tab_widget and hasattr(self._tab_widget, "add_new_tab"):
            view = self._tab_widget.add_new_tab()
            return view
        return None

    def contextMenuEvent(self, event):
        """Build custom right-click context menu based on what was clicked."""
        from . import style

        data = self.lastContextMenuRequest()
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {style.BG_CARD};
                color: {style.TEXT};
                border: 1px solid {style.BORDER};
                border-radius: 8px;
                padding: 4px 0px;
            }}
            QMenu::item {{
                padding: 6px 28px 6px 16px;
                border-radius: 4px;
                margin: 2px 4px;
            }}
            QMenu::item:selected {{
                background: {style.ACCENT};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: {style.BORDER};
                margin: 4px 12px;
            }}
        """)

        link_url = data.linkUrl()
        media_url = data.mediaUrl()
        selected_text = data.selectedText()
        media_type = data.mediaType()

        # Link actions
        if link_url.isValid():
            open_tab = menu.addAction("Open Link in New Tab")
            open_tab.triggered.connect(lambda: self._open_in_new_tab(link_url))
            copy_link = menu.addAction("Copy Link Address")
            copy_link.triggered.connect(lambda: QApplication.clipboard().setText(link_url.toString()))
            menu.addSeparator()

        # Image actions
        if media_type == QWebEngineContextMenuRequest.MediaType.MediaTypeImage and media_url.isValid():
            open_img = menu.addAction("Open Image in New Tab")
            open_img.triggered.connect(lambda: self._open_in_new_tab(media_url))
            copy_img = menu.addAction("Copy Image URL")
            copy_img.triggered.connect(lambda: QApplication.clipboard().setText(media_url.toString()))
            save_img = menu.addAction("Save Image As\u2026")
            save_img.triggered.connect(lambda: self.triggerPageAction(QWebEnginePage.WebAction.DownloadMediaToDisk))
            menu.addSeparator()

        # Video/media actions - PiP
        if media_type == QWebEngineContextMenuRequest.MediaType.MediaTypeVideo and media_url.isValid():
            pip_act = menu.addAction("Picture in Picture")
            pip_act.triggered.connect(lambda: self._toggle_pip())
            menu.addSeparator()

        # Selected text actions
        if selected_text:
            copy_act = menu.addAction("Copy")
            copy_act.triggered.connect(lambda: self.triggerPageAction(QWebEnginePage.WebAction.Copy))
            search_act = menu.addAction(f"Search for \"{selected_text[:30]}{'...' if len(selected_text) > 30 else ''}\"")
            search_act.triggered.connect(lambda: self._search_text(selected_text))
            menu.addSeparator()

        # Page-level actions (always present)
        back_act = menu.addAction("Back")
        back_act.triggered.connect(self.back)
        back_act.setEnabled(self.history().canGoBack())

        fwd_act = menu.addAction("Forward")
        fwd_act.triggered.connect(self.forward)
        fwd_act.setEnabled(self.history().canGoForward())

        reload_act = menu.addAction("Reload")
        reload_act.triggered.connect(self.reload)

        menu.addSeparator()

        select_all = menu.addAction("Select All")
        select_all.triggered.connect(lambda: self.triggerPageAction(QWebEnginePage.WebAction.SelectAll))

        view_source = menu.addAction("View Page Source")
        view_source.triggered.connect(lambda: self._view_source())

        # Watch page action
        current_url = self.url().toString()
        if current_url and not current_url.startswith("shroud:"):
            from . import storage as _st
            menu.addSeparator()
            if _st.is_watched(current_url):
                watch_act = menu.addAction("Stop Watching This Page")
                watch_act.triggered.connect(lambda: self._stop_watching())
            else:
                watch_act = menu.addAction("Watch This Page")
                watch_act.triggered.connect(lambda: self._start_watching())

        menu.exec(event.globalPos())

    def _open_in_new_tab(self, url):
        if self._tab_widget and hasattr(self._tab_widget, "add_new_tab"):
            self._tab_widget.add_new_tab(url)

    def _search_text(self, text):
        """Search selected text using the configured search engine."""
        if self._tab_widget and hasattr(self._tab_widget, "_settings"):
            search = self._tab_widget._settings.get(
                "search_engine", "https://duckduckgo.com/?q={}"
            )
            url = QUrl(search.format(QUrl.toPercentEncoding(text).data().decode()))
            self._open_in_new_tab(url)

    def _toggle_pip(self):
        """Toggle picture-in-picture for the focused video element."""
        js = """
        (function() {
            var video = document.querySelector('video');
            if (!video) return false;
            if (document.pictureInPictureElement) {
                document.exitPictureInPicture();
            } else {
                video.requestPictureInPicture();
            }
            return true;
        })()
        """
        self.page().runJavaScript(js)

    def _start_watching(self):
        if self._tab_widget and hasattr(self._tab_widget, "_add_page_watch"):
            self._tab_widget._add_page_watch(self)

    def _stop_watching(self):
        if self._tab_widget and hasattr(self._tab_widget, "_remove_page_watch"):
            self._tab_widget._remove_page_watch(self)

    def _view_source(self):
        if self._tab_widget and hasattr(self._tab_widget, "_view_source"):
            self._tab_widget._view_source()
