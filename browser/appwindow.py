"""Minimal PWA app window — no tabs, no URL bar, just the web content."""

import os

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from . import __app_name__, storage, style
from .adblock import AdBlockInterceptor
from .webview import ShroudWebView


class AppWindow(QMainWindow):
    """A minimal browser window for installed PWAs."""

    def __init__(self, url, dns_proxy=None):
        super().__init__()
        self._dns_proxy = dns_proxy
        self._settings = storage.load_settings()

        # Use a named profile so cookies/storage persist per-app
        profile_dir = str(storage.DATA_DIR / "webengine")
        cache_dir = str(storage.DATA_DIR / "cache")
        os.makedirs(profile_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)

        self._profile = QWebEngineProfile("shroudbyte", self)
        self._profile.setPersistentStoragePath(profile_dir)
        self._profile.setCachePath(cache_dir)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        # Ad blocker
        self._adblocker = AdBlockInterceptor(self)
        self._adblocker.enabled = self._settings.get("enable_adblock", True)
        self._profile.setUrlRequestInterceptor(self._adblocker)

        # Apply JS/UA settings
        ws = self._profile.settings()
        ws.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled,
            self._settings.get("enable_javascript", True),
        )
        if self._settings.get("user_agent"):
            self._profile.setHttpUserAgent(self._settings["user_agent"])

        # Window setup — minimal chrome
        self.setWindowTitle(__app_name__)
        self.resize(1024, 720)
        self.setStyleSheet(style.GLOBAL_STYLESHEET)

        # Single web view, no tabs
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._view = ShroudWebView(self._profile, tab_widget=None, parent=central)
        self._view.page().https_only = self._settings.get("https_only", False)
        self._view.titleChanged.connect(self._on_title_changed)
        layout.addWidget(self._view)

        self.setCentralWidget(central)

        # Navigate
        self._view.load(QUrl(url))

    def _on_title_changed(self, title):
        if title:
            self.setWindowTitle(title)

    def _current_view(self):
        return self._view
