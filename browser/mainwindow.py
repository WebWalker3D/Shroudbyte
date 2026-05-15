"""Main browser window with tabbed browsing, navigation, bookmarks, and history."""

import html as html_mod
import json
import os
import re
import signal
import sys
import time
from functools import partial

from PyQt6.QtCore import Qt, QUrl, QSize, QSortFilterProxyModel, QModelIndex, QEvent, QObject, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QFont, QPalette, QColor
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineSettings,
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from .reader import READER_EXTRACT_JS, generate_reader_html
from PyQt6.QtWidgets import (
    QApplication,
    QCompleter,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QStyledItemDelegate,
    QStyle,
    QTabBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QDialogButtonBox,
    QCheckBox,
    QSpinBox,
    QFormLayout,
    QMessageBox,
    QInputDialog,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from . import __app_name__, __version__, storage
from .adblock import AdBlockInterceptor
from .downloads import DownloadShelf
from . import filterlists
from .annoyance_shield import get_annoyance_shield_js
from .clipboard_history import ClipboardHistory
from .fingerprint import get_fingerprint_resistance_js
from .passwords import PasswordVault
from .passworddialogs import (
    AutofillBar,
    HttpAuthDialog,
    MasterPasswordDialog,
    PasswordManagerDialog,
    PasswordSaveBar,
)
from .scheme import ShroudSchemeHandler
from .webview import ShroudWebView
from .link_intel import LinkResolver
from .pagewatcher import PageWatcher
from .pwa import detect_manifest_js, install_pwa, uninstall_pwa
from .background_activity import BackgroundActivityManager
from .extensions import ExtensionManager
from .screentime import ScreenTimeTracker
from .warc_capture import WarcCapture
from .privacy_panel import PrivacyPanel
from . import style
from .mixins import (
    TabMixin,
    NavigationMixin,
    ContentBlockingMixin,
    PasswordMixin,
    PageFeaturesMixin,
    SettingsMixin,
    BrowserActionsMixin,
    DataManagementMixin,
    SessionMixin,
)


class _SubstringFilterModel(QSortFilterProxyModel):
    """Proxy model that matches when the filter string appears *anywhere* in the row."""

    _cached_pattern = ""

    def setFilterFixedString(self, pattern):
        self._cached_pattern = pattern.lower()
        super().setFilterFixedString(pattern)

    def filterAcceptsRow(self, source_row, source_parent):
        pattern = self._cached_pattern
        if not pattern:
            return True
        model = self.sourceModel()
        idx = model.index(source_row, 0, source_parent)
        url = (model.data(idx, Qt.ItemDataRole.DisplayRole) or "").lower()
        if pattern in url:
            return True
        title = (model.data(idx, Qt.ItemDataRole.UserRole + 1) or "").lower()
        return pattern in title


class _SuggestionDelegate(QStyledItemDelegate):
    """Two-line delegate: title on top (dimmer), URL on bottom."""

    def paint(self, painter, option, index):
        painter.save()
        self.initStyleOption(option, index)

        url = index.data(Qt.ItemDataRole.DisplayRole) or ""
        title = index.data(Qt.ItemDataRole.UserRole + 1) or ""

        # Draw selection / hover background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(style.ACCENT))
            url_color = QColor("white")
            title_color = QColor(220, 220, 230)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(style.BG_HOVER))
            url_color = QColor(style.TEXT)
            title_color = QColor(style.TEXT_DIM)
        else:
            url_color = QColor(style.TEXT)
            title_color = QColor(style.TEXT_DIM)

        left = option.rect.left() + 10
        right = option.rect.right() - 10

        if title:
            # Title line
            painter.setPen(title_color)
            title_rect = option.rect.adjusted(10, 4, -10, -option.rect.height() // 2)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             option.fontMetrics.elidedText(title, Qt.TextElideMode.ElideRight, right - left))
            # URL line
            painter.setPen(url_color)
            url_rect = option.rect.adjusted(10, option.rect.height() // 2, -10, -4)
            painter.drawText(url_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             option.fontMetrics.elidedText(url, Qt.TextElideMode.ElideRight, right - left))
        else:
            # URL only, centred vertically
            painter.setPen(url_color)
            painter.drawText(option.rect.adjusted(10, 0, -10, 0),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             option.fontMetrics.elidedText(url, Qt.TextElideMode.ElideRight, right - left))

        painter.restore()

    def sizeHint(self, option, index):
        title = index.data(Qt.ItemDataRole.UserRole + 1)
        if title:
            return QSize(0, 44)
        return QSize(0, 30)


class _CopyEventFilter(QObject):
    """App-level event filter that catches Ctrl+C for clipboard history.

    Installed on QApplication so it sees key events before Chromium's
    internal widget can consume them.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self._mw = main_window

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_C
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            view = self._mw._current_view()
            if view and hasattr(view, "page"):
                url = view.url().toString()
                ch = self._mw._clipboard_history
                view.page().runJavaScript(
                    "window.getSelection().toString()",
                    lambda text: ch.record(text, url) if text else None,
                )
        return False  # never consume — let the actual copy happen


class MainWindow(
    TabMixin,
    NavigationMixin,
    ContentBlockingMixin,
    PasswordMixin,
    PageFeaturesMixin,
    SettingsMixin,
    BrowserActionsMixin,
    DataManagementMixin,
    SessionMixin,
    QMainWindow,
):
    # Signal for thread-safe delivery of link intelligence results.
    # Emitted from the resolver's background thread; the connected slot
    # runs on the GUI thread automatically via Qt's queued connection.
    from PyQt6.QtCore import pyqtSignal
    _link_resolved_sig = pyqtSignal(object, object)
    _suggestions_ready_sig = pyqtSignal(list)

    def __init__(self, dns_proxy=None, private_mode=False):
        super().__init__()
        self._link_resolved_sig.connect(self._on_link_resolved)
        self._dns_proxy = dns_proxy

        self._settings = storage.load_settings()
        self._private_mode = private_mode or self._settings.get("private_mode", False)

        # Profile
        if self._private_mode:
            self._profile = QWebEngineProfile(self)
        else:
            # Use a named profile so persistent storage paths are honoured.
            # The default profile ignores setPersistentStoragePath on some
            # Qt/PyQt6 versions, causing all session data to be lost.
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

        # Spellcheck — uses Chromium's built-in dictionary support. Language
        # follows the system locale unless the user overrode it in settings.
        if self._settings.get("spellcheck_enabled", True):
            self._profile.setSpellCheckEnabled(True)
            langs = self._settings.get("spellcheck_languages", [])
            if not langs:
                import locale as _locale
                sys_lang = (_locale.getdefaultlocale()[0] or "en_US")
                langs = [sys_lang]
            self._profile.setSpellCheckLanguages(langs)

        self._apply_profile_settings()

        # shroud:// scheme handler
        self._scheme_handler = ShroudSchemeHandler(self._profile, parent=self)
        self._profile.installUrlSchemeHandler(b"shroud", self._scheme_handler)

        # Ad blocker
        self._adblocker = AdBlockInterceptor(self)
        self._adblocker.enabled = self._settings.get("enable_adblock", True)
        self._profile.setUrlRequestInterceptor(self._adblocker)

        # Load per-site tracker exceptions for the Privacy Dashboard
        self._adblocker.set_site_exceptions(storage.load_site_exceptions())

        # Link Intelligence resolver
        self._link_resolver = LinkResolver(self._adblocker._blocked_hosts)

        # Page Watcher
        self._page_watcher = PageWatcher(self)
        self._page_watcher.page_changed.connect(self._on_page_watch_changed)

        # Screen Time Tracker
        self._screen_time = ScreenTimeTracker(self)
        self._screen_time.start(
            self._settings.get("screen_time_tracking", False),
            self._private_mode,
        )

        # Background Activity Manager
        self._bg_activity = BackgroundActivityManager(self)

        # Extension Manager (content script system)
        self._extension_manager = ExtensionManager()

        # WARC/WACZ Capture
        self._warc_capture = WarcCapture()

        # Clipboard History (in-memory only, dies with session)
        self._clipboard_history = ClipboardHistory(
            get_current_url=lambda: (
                self._current_view().url().toString()
                if self._current_view() else ""
            ),
        )
        self._clipboard_history.set_enabled(
            self._settings.get("clipboard_history", True) and not self._private_mode
        )
        self._copy_filter = _CopyEventFilter(self)
        QApplication.instance().installEventFilter(self._copy_filter)

        # Early content-blocking script (runs at document creation before page scripts)
        if self._settings.get("enable_adblock", True):
            self._install_content_blocking_script()

        # Downloads
        self._download_shelf = DownloadShelf(self)
        self._profile.downloadRequested.connect(self._download_shelf.handle_download)

        # Password vault
        self._vault = PasswordVault()
        if self._settings.get("vault_backend") == "keyring":
            self._vault.unlock_with_keyring()
        self._password_save_bar = None

        # Vault auto-lock timer (resets on user interaction)
        from PyQt6.QtCore import QTimer
        self._vault_lock_timer = QTimer(self)
        self._vault_lock_timer.setSingleShot(True)
        self._vault_lock_timer.timeout.connect(self._auto_lock_vault)
        self._reset_vault_lock_timer()
        self._autofill_bar = None

        # Closed tabs stack (for Ctrl+Shift+T)
        self._closed_tabs = []

        # Container profiles
        from .profiles import ProfileManager
        self._profile_manager = ProfileManager(parent=self)

        # Window setup
        self.setWindowTitle(__app_name__)
        self._restore_window_state_mode = "normal"
        ws = storage.load_window_state() if not private_mode else {}
        if ws:
            w = int(ws.get("width", 1280))
            h = int(ws.get("height", 900))
            if "x" in ws and "y" in ws:
                x, y = int(ws["x"]), int(ws["y"])
                # Multi-monitor safety: if the saved position is on a screen
                # that no longer exists (laptop undocked, external unplugged),
                # the window would land off-screen and be unreachable. Verify
                # the geometry overlaps at least one current screen.
                from PyQt6.QtWidgets import QApplication
                from PyQt6.QtCore import QRect
                target = QRect(x, y, w, h)
                visible = any(
                    s.availableGeometry().intersects(target)
                    for s in QApplication.screens()
                )
                if visible:
                    self.setGeometry(x, y, w, h)
                else:
                    self.resize(w, h)
            else:
                self.resize(w, h)
            mode = ws.get("state", "normal")
            if mode in ("maximized", "fullscreen"):
                self._restore_window_state_mode = mode
        else:
            self.resize(1280, 900)
        self.setStyleSheet(style.GLOBAL_STYLESHEET)
        self._setup_ui()
        self._setup_menus()
        self._setup_shortcuts()

        # Track cookies from startup for the cookie manager
        self._all_cookies: list = []
        cs = self._profile.cookieStore()
        cs.cookieAdded.connect(self._on_cookie_added)
        cs.cookieRemoved.connect(self._on_cookie_removed)
        cs.loadAllCookies()

        # Auto-hide menu bar
        self.menuBar().setVisible(False)
        self._menu_visible = False
        self.menuBar().triggered.connect(self._on_menu_action_triggered)

        # Apply privacy settings
        self._adblocker.do_not_track = self._settings.get("do_not_track", True)
        self._adblocker.strip_tracking = self._settings.get("strip_tracking", True)

        # Defer heavy filter list parsing until after the window is visible.
        # The hardcoded defaults protect during the brief loading window.
        self._cosmetic_css = ""

        # Session restore or new tab
        self._restore_session_or_new_tab()

        # Load filter lists in background after the UI is up
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._deferred_filter_load)

        # Autosave session every 30 seconds so data survives crashes
        from PyQt6.QtCore import QTimer
        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._autosave_session)
        self._session_timer.start(30_000)

        # Auto-update filter lists every 24 hours
        self._filterlist_timer = QTimer(self)
        self._filterlist_timer.timeout.connect(self._auto_update_filterlists)
        self._filterlist_timer.start(24 * 60 * 60 * 1000)
        QTimer.singleShot(5000, self._check_filterlist_freshness)

        # Start page watcher after startup settles
        QTimer.singleShot(10_000, self._page_watcher.start)

        # Handle SIGTERM / SIGINT so session is saved on kill
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _deferred_filter_load(self):
        """Load filter lists in a thread after the window is visible."""
        import threading

        def _worker():
            # Do ALL heavy work in the background thread
            custom = storage.load_blocked_hosts()
            filter_hosts = filterlists.get_all_blocked_hosts()
            from .adblock import DEFAULT_BLOCKED
            blocked = DEFAULT_BLOCKED | custom | filter_hosts
            css = filterlists.get_cosmetic_css()
            abp_lines = filterlists.get_all_abp_lines()

            # Only assign results on the GUI thread — no parsing, no I/O
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._apply_filter_results(blocked, css, abp_lines))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_filter_results(self, blocked_hosts, cosmetic_css, abp_lines=None):
        """Apply pre-computed filter results on the GUI thread (fast)."""
        self._adblocker._blocked_hosts = blocked_hosts
        self._link_resolver.update_blocked_hosts(blocked_hosts)
        self._cosmetic_css = cosmetic_css
        # Initialize the enhanced ABP engine with parsed filter rules
        if abp_lines:
            from .adblock_engine import AdBlockEngine
            engine = AdBlockEngine()
            engine.parse_rules(abp_lines)
            self._adblocker._engine = engine
        self._update_adblock_label()

    # ------------------------------------------------------------------
    # Profile / settings helpers
    # ------------------------------------------------------------------

    def _restart_browser(self):
        """Save state and re-exec the browser process."""
        self._autosave_session()
        if self._dns_proxy is not None:
            self._dns_proxy.stop()
        os.execv(sys.executable, [sys.executable, "-m", "browser"])

    def _apply_profile_settings(self):
        settings = self._profile.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled,
            self._settings.get("enable_javascript", True),
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.PluginsEnabled, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.WebGLEnabled, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True
        )

        ua = self._settings.get("user_agent", "")
        if ua:
            self._profile.setHttpUserAgent(ua)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # --- Navigation toolbar ---
        self._navbar = QToolBar("Navigation")
        self._navbar.setMovable(False)
        self._navbar.setIconSize(QSize(18, 18))
        self.addToolBar(self._navbar)

        # --- Bookmark bar (hidden by default; toggle in Bookmarks menu) ---
        self._bookmark_bar = QToolBar("Bookmarks Bar")
        self._bookmark_bar.setMovable(False)
        self._bookmark_bar.setIconSize(QSize(16, 16))
        self._bookmark_bar.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.addToolBarBreak()
        self.addToolBar(self._bookmark_bar)
        self._bookmark_bar.setVisible(
            bool(self._settings.get("show_bookmark_bar", False))
        )

        self._back_btn = QPushButton("\u25C0")
        self._back_btn.setToolTip("Back")
        self._back_btn.setStyleSheet(style.NAV_BTN_STYLE)
        self._back_btn.clicked.connect(lambda: self._current_view().back())

        self._forward_btn = QPushButton("\u25B6")
        self._forward_btn.setToolTip("Forward")
        self._forward_btn.setStyleSheet(style.NAV_BTN_STYLE)
        self._forward_btn.clicked.connect(lambda: self._current_view().forward())

        self._reload_btn = QPushButton("\u21BB")
        self._reload_btn.setToolTip("Reload")
        self._reload_btn.setStyleSheet(style.NAV_BTN_STYLE)
        self._reload_btn.clicked.connect(lambda: self._current_view().reload())

        self._home_btn = QPushButton("\u2302")
        self._home_btn.setToolTip("Home")
        self._home_btn.setStyleSheet(style.NAV_BTN_STYLE)
        self._home_btn.clicked.connect(self._go_home)

        # Security indicator (clickable for per-site controls)
        self._security_icon = QPushButton()
        self._security_icon.setFixedSize(24, 24)
        self._security_icon.setFlat(True)
        self._security_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._security_icon.setToolTip("Connection security — click for site controls")
        self._security_icon.setStyleSheet(f"color: {style.TEXT_FAINT}; font-size: 14px; padding: 0;")
        self._security_icon.clicked.connect(self._show_site_controls)

        # URL bar
        self._url_bar = QLineEdit()
        self._url_bar.setPlaceholderText("Search or enter URL\u2026")
        self._url_bar.setStyleSheet(style.URL_BAR_STYLE)
        self._url_bar.returnPressed.connect(self._navigate_to_url)

        # --- URL autocomplete ---
        self._completer_model = QStandardItemModel(self)
        self._completer_proxy = _SubstringFilterModel(self)
        self._completer_proxy.setSourceModel(self._completer_model)
        self._completer_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._url_completer = QCompleter(self)
        self._url_completer.setModel(self._completer_proxy)
        self._url_completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._url_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._url_completer.setMaxVisibleItems(10)
        self._url_completer.setCompletionRole(Qt.ItemDataRole.DisplayRole)

        popup = self._url_completer.popup()
        popup.setStyleSheet(style.COMPLETER_POPUP_STYLE)
        popup.setItemDelegate(_SuggestionDelegate(popup))

        self._url_bar.setCompleter(self._url_completer)
        self._url_completer.activated[QModelIndex].connect(self._on_completion_activated)
        self._url_bar.textChanged.connect(self._filter_completions)

        self._refresh_suggestions()

        self._bookmark_btn = QPushButton("\u2606")
        self._bookmark_btn.setToolTip("Bookmark this page")
        self._bookmark_btn.setStyleSheet(style.BOOKMARK_BTN_STYLE)
        self._bookmark_btn.clicked.connect(self._toggle_bookmark)

        self._reader_btn = QPushButton("Aa")
        self._reader_btn.setToolTip("Reader Mode (F9)")
        self._reader_btn.setStyleSheet(style.NAV_BTN_STYLE)
        self._reader_btn.clicked.connect(self._toggle_reader_mode)

        self._new_tab_btn = QPushButton("+")
        self._new_tab_btn.setToolTip("New Tab (Ctrl+T)")
        self._new_tab_btn.setStyleSheet(style.NEW_TAB_BTN_STYLE)
        self._new_tab_btn.clicked.connect(lambda: self.add_new_tab())

        self._capture_btn = QPushButton("\u23fa")
        self._capture_btn.setToolTip("Start/Stop WARC Capture")
        self._capture_btn.setStyleSheet(style.NAV_BTN_STYLE)
        self._capture_btn.clicked.connect(self._toggle_capture)

        for w in [
            self._back_btn, self._forward_btn, self._reload_btn,
            self._home_btn, self._security_icon, self._url_bar,
            self._bookmark_btn, self._reader_btn, self._capture_btn,
            self._new_tab_btn,
        ]:
            self._navbar.addWidget(w)

        # --- Tab widget ---
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._tab_changed)

        # Right-click context menu on tabs
        self._tabs.tabBar().setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._tabs.tabBar().customContextMenuRequested.connect(
            self._tab_context_menu
        )

        # Central container (progress bar + tabs + find bar)
        central = QWidget()
        self._central_layout = QVBoxLayout(central)
        self._central_layout.setContentsMargins(0, 0, 0, 0)
        self._central_layout.setSpacing(0)

        # Full-width loading bar pinned under the toolbar
        self._progress = QProgressBar()
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        self._central_layout.addWidget(self._progress)

        self._central_layout.addWidget(self._tabs)

        # Download shelf (hidden by default, shown when a download starts)
        self._central_layout.addWidget(self._download_shelf)

        # Find bar (hidden by default)
        self._find_bar = self._create_find_bar()
        self._find_bar.setVisible(False)
        self._central_layout.addWidget(self._find_bar)

        self.setCentralWidget(central)

        # --- Status bar ---
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._reading_time_label = QLabel()
        self._reading_time_label.setStyleSheet(
            f"color: {style.TEXT_FAINT}; font-size: 11px; padding: 0 8px;"
        )
        self._reading_time_label.setVisible(False)
        self._status.addPermanentWidget(self._reading_time_label)

        self._watch_label = QPushButton()
        self._watch_label.setFlat(True)
        self._watch_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._watch_label.clicked.connect(
            lambda: self.add_new_tab(QUrl("shroud://watches"))
        )
        self._status.addPermanentWidget(self._watch_label)
        self._update_watch_indicator()

        self._adblock_label = QPushButton()
        self._adblock_label.setFlat(True)
        self._adblock_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._adblock_label.clicked.connect(self._show_privacy_panel)
        self._status.addPermanentWidget(self._adblock_label)
        self._update_adblock_label()

    def _make_action(self, text, slot, shortcut=None, parent=None):
        """Helper to create a QAction with proper PyQt6 API."""
        action = QAction(text, parent or self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            # Register on the window so shortcuts work even when
            # the menu bar is hidden.
            self.addAction(action)
        return action

    def _setup_menus(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self._make_action("New Tab", lambda: self.add_new_tab(), "Ctrl+T"))
        file_menu.addAction(self._make_action("Reopen Closed Tab", self._reopen_closed_tab, "Ctrl+Shift+T"))
        file_menu.addAction(self._make_action("Close Tab", self._close_current_tab, "Ctrl+W"))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("New Window", self._open_new_window, "Ctrl+N"))
        file_menu.addAction(self._make_action("New Private Window", self._open_private_window, "Ctrl+Shift+P"))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Save Page Offline", self._quick_save_page, "Ctrl+Shift+D"))
        file_menu.addAction(self._make_action("Print\u2026", self._print_page, "Ctrl+P"))
        file_menu.addAction(self._make_action("Save as PDF\u2026", self._save_pdf, "Ctrl+Shift+S"))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Sessions", lambda: self.add_new_tab(QUrl("shroud://sessions"))))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Export Data\u2026", self._export_browser_data))
        file_menu.addAction(self._make_action("Import Data\u2026", self._import_browser_data))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Quit", self.close, "Ctrl+Q"))

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self._make_action("Zoom In", self._zoom_in, "Ctrl+="))
        view_menu.addAction(self._make_action("Zoom Out", self._zoom_out, "Ctrl+-"))
        view_menu.addAction(self._make_action("Reset Zoom", self._zoom_reset, "Ctrl+0"))
        view_menu.addSeparator()
        view_menu.addAction(self._make_action("Full Screen", self._toggle_fullscreen, "F11"))
        view_menu.addSeparator()
        view_menu.addAction(self._make_action("Reader Mode", self._toggle_reader_mode, "F9"))
        view_menu.addSeparator()
        view_menu.addAction(self._make_action("View Source", self._view_source, "Ctrl+U"))
        view_menu.addSeparator()
        view_menu.addAction(self._make_action("Search Tabs", self._show_tab_search, "Ctrl+Shift+F"))
        view_menu.addAction(self._make_action("Group Tabs by Site", self._group_tabs_by_domain, "Ctrl+Shift+G"))
        view_menu.addSeparator()
        view_menu.addAction(self._make_action("Picture in Picture", self._toggle_pip))

        # Bookmarks menu
        bm_menu = menubar.addMenu("&Bookmarks")
        bm_menu.addAction(self._make_action("Bookmark This Page", self._toggle_bookmark, "Ctrl+D"))
        bm_menu.addAction(self._make_action("Show All Bookmarks", self._show_bookmarks, "Ctrl+Shift+B"))
        bm_menu.addAction(self._make_action(
            "Toggle Bookmarks Bar", self._toggle_bookmark_bar, "Ctrl+Alt+B"
        ))
        bm_menu.addSeparator()
        bm_menu.addAction(self._make_action("Import Bookmarks\u2026", self._import_bookmarks))
        bm_menu.addAction(self._make_action("Export Bookmarks\u2026", self._export_bookmarks))
        bm_menu.addSeparator()
        self._bookmarks_menu = bm_menu
        self._populate_bookmarks_menu()

        # History menu
        hist_menu = menubar.addMenu("&History")
        hist_menu.addAction(self._make_action("Show History", self._show_history, "Ctrl+H"))
        hist_menu.addAction(self._make_action("Clear History", self._clear_history))

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        # -- Privacy & Security submenu --
        privacy_menu = tools_menu.addMenu("Privacy && Security")
        privacy_menu.addAction(self._make_action("Privacy Dashboard",
            lambda: self.add_new_tab(QUrl("shroud://privacy"))))
        privacy_menu.addAction(self._make_action("Cookie Manager", self._show_cookie_manager))
        privacy_menu.addAction(self._make_action("Site Permissions\u2026", self._show_permissions))
        privacy_menu.addAction(self._make_action("Filter Lists\u2026", self._show_filter_lists))
        privacy_menu.addSeparator()
        privacy_menu.addAction(self._make_action("Clear Browsing Data\u2026", self._show_clear_data))

        # -- Passwords submenu --
        passwords_menu = tools_menu.addMenu("Passwords")
        passwords_menu.addAction(self._make_action("Password Manager", self._show_password_manager, "Ctrl+Shift+M"))
        passwords_menu.addAction(self._make_action("Auto-fill Password", self._auto_fill_password, "Ctrl+Shift+L"))

        # -- Page Tools submenu --
        page_menu = tools_menu.addMenu("Page Tools")
        page_menu.addAction(self._make_action("Screenshot\u2026", self._take_screenshot, "Ctrl+Shift+E"))
        page_menu.addAction(self._make_action("Capture Mode", self._toggle_capture))
        page_menu.addAction(self._make_action("Captures",
            lambda: self.add_new_tab(QUrl("shroud://captures"))))
        page_menu.addSeparator()
        page_menu.addAction(self._make_action("Saved Pages",
            lambda: self.add_new_tab(QUrl("shroud://saved"))))
        page_menu.addAction(self._make_action("Page Watches",
            lambda: self.add_new_tab(QUrl("shroud://watches"))))

        tools_menu.addSeparator()

        # -- Top-level items --
        tools_menu.addAction(self._make_action("Downloads", self._show_downloads, "Ctrl+J"))
        tools_menu.addAction(self._make_action("Extensions",
            lambda: self.add_new_tab(QUrl("shroud://extensions"))))
        tools_menu.addAction(self._make_action("Profiles",
            lambda: self.add_new_tab(QUrl("shroud://profiles"))))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Screen Time",
            lambda: self.add_new_tab(QUrl("shroud://screentime"))))
        tools_menu.addAction(self._make_action("Background Activity",
            lambda: self.add_new_tab(QUrl("shroud://background"))))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Developer Tools", self._open_devtools, "F12"))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Settings", self._show_settings))

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self._make_action(
            "Keyboard Shortcuts", lambda: self._current_view().load(QUrl("shroud://shortcuts")), "F1"))
        help_menu.addSeparator()
        help_menu.addAction(self._make_action("About", self._show_about))

    def _setup_shortcuts(self):
        for i in range(9):
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Alt+{i + 1}"))
            action.triggered.connect(partial(self._switch_to_tab, i))
            self.addAction(action)

        focus_url = QAction(self)
        focus_url.setShortcut(QKeySequence("Ctrl+L"))
        focus_url.triggered.connect(self._focus_url_bar)
        self.addAction(focus_url)

        alt_focus = QAction(self)
        alt_focus.setShortcut(QKeySequence("F6"))
        alt_focus.triggered.connect(self._focus_url_bar)
        self.addAction(alt_focus)

        find_action = QAction(self)
        find_action.setShortcut(QKeySequence("Ctrl+F"))
        find_action.triggered.connect(self._find_on_page)
        self.addAction(find_action)

        reload_action = QAction(self)
        reload_action.setShortcut(QKeySequence("F5"))
        reload_action.triggered.connect(lambda: self._current_view().reload())
        self.addAction(reload_action)

        reload_ctrl = QAction(self)
        reload_ctrl.setShortcut(QKeySequence("Ctrl+R"))
        reload_ctrl.triggered.connect(lambda: self._current_view().reload())
        self.addAction(reload_ctrl)

        hard_reload = QAction(self)
        hard_reload.setShortcut(QKeySequence("Ctrl+Shift+R"))
        hard_reload.triggered.connect(self._hard_reload)
        self.addAction(hard_reload)

        stop_action = QAction(self)
        stop_action.setShortcut(QKeySequence("Escape"))
        stop_action.triggered.connect(lambda: self._current_view().stop())
        self.addAction(stop_action)

        tab_search = QAction(self)
        tab_search.setShortcut(QKeySequence("Ctrl+Shift+F"))
        tab_search.triggered.connect(self._show_tab_search)
        self.addAction(tab_search)

        save_page = QAction(self)
        save_page.setShortcut(QKeySequence("Ctrl+Shift+D"))
        save_page.triggered.connect(self._quick_save_page)
        self.addAction(save_page)

        cmd_palette = QAction(self)
        cmd_palette.setShortcut(QKeySequence("Ctrl+K"))
        cmd_palette.triggered.connect(self._show_command_palette)
        self.addAction(cmd_palette)

    # ------------------------------------------------------------------
    # Auto-hide menu bar
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        # Escape closes find bar if visible
        if event.key() == Qt.Key.Key_Escape and self._find_bar.isVisible():
            self._close_find_bar()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        # Alt toggles menu bar visibility (on release to avoid
        # conflicting with Qt's built-in Alt menu activation).
        if event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat():
            if not self._menu_visible:
                self.menuBar().setVisible(True)
                self._menu_visible = True
            else:
                self.menuBar().setVisible(False)
                self._menu_visible = False
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _on_menu_action_triggered(self, action):
        """Hide menu bar after a menu action is used."""
        self.menuBar().setVisible(False)
        self._menu_visible = False
