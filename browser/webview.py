"""Custom WebEngineView and WebEnginePage with context menus, HTTPS-only, and popup support."""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineContextMenuRequest,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QVBoxLayout


class BladePage(QWebEnginePage):
    """Custom page that handles new-window requests and HTTPS-only mode."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._view_ref = None
        self.https_only = False

    def createWindow(self, window_type):
        view = self._view_ref
        if view and hasattr(view, "create_window_requested"):
            new_view = view.create_window_requested()
            if new_view is not None:
                return new_view.page()
        return None

    def certificateError(self, error):
        return True

    # Loopback IPs that Chromium blocks when a SOCKS proxy is active.
    # Rewrite them to "localhost" which Chromium allows through.
    _LOOPBACK_IPS = {"127.0.0.1", "::1", "[::1]"}

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        """Rewrite loopback IPs to localhost and upgrade http to https."""
        host = url.host()

        # Chromium blocks raw loopback IPs through a proxy — rewrite to
        # "localhost" which is excluded from proxy and resolves the same.
        # Guard against re-entry: only rewrite if host is still an IP.
        if is_main_frame and host in self._LOOPBACK_IPS:
            rewritten = QUrl(url)
            rewritten.setHost("localhost")
            # Use QTimer.singleShot to break out of the navigation call stack
            # and avoid re-entrant setUrl inside acceptNavigationRequest.
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda u=rewritten: self.setUrl(u))
            return False

        if self.https_only and url.scheme() == "http" and is_main_frame:
            # Don't upgrade localhost / local network
            if host not in ("localhost", "127.0.0.1", "::1") and not host.endswith(".local"):
                secure = QUrl(url)
                secure.setScheme("https")
                self.setUrl(secure)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class BladeWebView(QWebEngineView):
    """WebEngineView subclass with tab integration and context menus."""

    def __init__(self, profile, tab_widget=None, parent=None):
        super().__init__(parent)
        self._tab_widget = tab_widget
        page = BladePage(profile, self)
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

        data = self.page().contextMenuData()
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

    def _view_source(self):
        if self._tab_widget and hasattr(self._tab_widget, "_view_source"):
            self._tab_widget._view_source()
