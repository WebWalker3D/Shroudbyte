"""Main browser window with tabbed browsing, navigation, bookmarks, and history."""

import html as html_mod
import json
import os
import re
import signal
import sys
import time
from functools import partial

from PyQt6.QtCore import Qt, QUrl, QSize, QSortFilterProxyModel, QModelIndex
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
from .fingerprint import get_fingerprint_resistance_js
from .passwords import PasswordVault
from .passworddialogs import (
    HttpAuthDialog,
    MasterPasswordDialog,
    PasswordManagerDialog,
    PasswordSaveBar,
)
from .scheme import ShroudSchemeHandler
from .webview import ShroudWebView
from . import style


class _SubstringFilterModel(QSortFilterProxyModel):
    """Proxy model that matches when the filter string appears *anywhere* in the row."""

    def filterAcceptsRow(self, source_row, source_parent):
        pattern = self.filterRegularExpression().pattern().lower()
        if not pattern:
            return True
        model = self.sourceModel()
        # Check both the URL (column 0) and title (Qt.UserRole+1 stored in column 0)
        idx = model.index(source_row, 0, source_parent)
        url = (model.data(idx, Qt.ItemDataRole.DisplayRole) or "").lower()
        title = (model.data(idx, Qt.ItemDataRole.UserRole + 1) or "").lower()
        return pattern in url or pattern in title


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


class MainWindow(QMainWindow):
    def __init__(self, dns_proxy=None):
        super().__init__()
        self._dns_proxy = dns_proxy

        self._settings = storage.load_settings()
        self._private_mode = self._settings.get("private_mode", False)

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

        self._apply_profile_settings()

        # shroud:// scheme handler
        self._scheme_handler = ShroudSchemeHandler(self._profile, parent=self)
        self._profile.installUrlSchemeHandler(b"shroud", self._scheme_handler)

        # Ad blocker
        self._adblocker = AdBlockInterceptor(self)
        self._adblocker.enabled = self._settings.get("enable_adblock", True)
        self._profile.setUrlRequestInterceptor(self._adblocker)

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

        # Closed tabs stack (for Ctrl+Shift+T)
        self._closed_tabs = []

        # Window setup
        self.setWindowTitle(__app_name__)
        self.resize(1280, 900)
        self.setStyleSheet(style.GLOBAL_STYLESHEET)
        self._setup_ui()
        self._setup_menus()
        self._setup_shortcuts()

        # Track cookies from startup for the cookie manager
        from PyQt6.QtNetwork import QNetworkCookie
        self._all_cookies: list = []
        cs = self._profile.cookieStore()
        cs.cookieAdded.connect(
            lambda c: self._all_cookies.append(QNetworkCookie(c))
        )
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

        # Handle SIGTERM / SIGINT so session is saved on kill
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Save session and exit on SIGTERM/SIGINT."""
        self._autosave_session()
        self._vault.lock()
        QApplication.quit()

    def _deferred_filter_load(self):
        """Load filter lists in a thread after the window is visible."""
        import threading

        def _load():
            filterlists.get_all_blocked_hosts()
            filterlists.get_cosmetic_css()

        def _apply():
            self._adblocker.reload_hosts()
            self._cosmetic_css = filterlists.get_cosmetic_css()
            self._update_adblock_label()

        def _worker():
            _load()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, _apply)

        threading.Thread(target=_worker, daemon=True).start()

    def _autosave_session(self):
        """Periodically save the current session to disk."""
        if not self._settings.get("restore_session", True) or self._private_mode:
            return
        tabs = []
        for i in range(self._tabs.count()):
            view = self._tabs.widget(i)
            if view:
                deferred = getattr(view, "_deferred_url", None)
                url = deferred or view.url().toString()
                title = view.title() or self._tabs.tabText(i)
                if url and not url.startswith("shroud:"):
                    tabs.append({
                        "url": url, "title": title,
                        "pinned": getattr(view, '_pinned', False),
                    })
        if tabs:
            storage.save_session(tabs)

    # ------------------------------------------------------------------
    # Profile / settings helpers
    # ------------------------------------------------------------------

    def _restart_browser(self):
        """Save state and re-exec the browser process."""
        self._autosave_session()
        if self._dns_proxy is not None:
            self._dns_proxy.stop()
        from . import __main__ as _main
        _main.release_single_instance_lock()
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

        # Security indicator
        self._security_icon = QLabel()
        self._security_icon.setFixedSize(24, 24)
        self._security_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._security_icon.setToolTip("Connection security")
        self._security_icon.setStyleSheet(f"color: {style.TEXT_FAINT}; font-size: 14px; padding: 0;")

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

        for w in [
            self._back_btn, self._forward_btn, self._reload_btn,
            self._home_btn, self._security_icon, self._url_bar,
            self._bookmark_btn, self._reader_btn, self._new_tab_btn,
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

        self._adblock_label = QLabel()
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
        file_menu.addAction(self._make_action("Print\u2026", self._print_page, "Ctrl+P"))
        file_menu.addAction(self._make_action("Save as PDF\u2026", self._save_pdf, "Ctrl+Shift+S"))
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
        view_menu.addAction(self._make_action("Picture in Picture", self._toggle_pip))

        # Bookmarks menu
        bm_menu = menubar.addMenu("&Bookmarks")
        bm_menu.addAction(self._make_action("Bookmark This Page", self._toggle_bookmark, "Ctrl+D"))
        bm_menu.addAction(self._make_action("Show All Bookmarks", self._show_bookmarks, "Ctrl+Shift+B"))
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
        tools_menu.addAction(self._make_action("Password Manager", self._show_password_manager, "Ctrl+Shift+M"))
        tools_menu.addAction(self._make_action("Auto-fill Password", self._auto_fill_password, "Ctrl+Shift+L"))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Filter Lists\u2026", self._show_filter_lists))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Downloads", self._show_downloads, "Ctrl+J"))
        tools_menu.addAction(self._make_action("Developer Tools", self._open_devtools, "F12"))
        tools_menu.addAction(self._make_action("Screenshot\u2026", self._take_screenshot, "Ctrl+Shift+E"))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Cookie Manager", self._show_cookie_manager))
        tools_menu.addAction(self._make_action("Site Permissions\u2026", self._show_permissions))
        tools_menu.addSeparator()
        tools_menu.addAction(self._make_action("Clear Browsing Data\u2026", self._show_clear_data))
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

    # ------------------------------------------------------------------
    # Tab context menu
    # ------------------------------------------------------------------

    def _tab_context_menu(self, pos):
        """Show right-click context menu for tabs."""
        index = self._tabs.tabBar().tabAt(pos)
        if index < 0:
            return

        menu = QMenu(self)

        view = self._tabs.widget(index)
        if getattr(view, '_pinned', False):
            menu.addAction("Unpin Tab", lambda: self._unpin_tab(index))
        else:
            menu.addAction("Pin Tab", lambda: self._pin_tab(index))

        if getattr(view, '_muted', False):
            menu.addAction("Unmute Tab", lambda: self._toggle_tab_mute(index))
        else:
            menu.addAction("Mute Tab", lambda: self._toggle_tab_mute(index))

        menu.addAction("Detach Tab", lambda: self._detach_tab(index))
        menu.addSeparator()
        menu.addAction("Close Tab", lambda: self._close_tab(index))
        menu.addAction("Close Other Tabs", lambda: self._close_other_tabs(index))
        menu.exec(self._tabs.tabBar().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Tab pinning
    # ------------------------------------------------------------------

    def _pin_tab(self, index):
        """Pin a tab: shrink it to icon-only, move to the left, remove close button."""
        view = self._tabs.widget(index)
        if not view or getattr(view, '_pinned', False):
            return
        view._pinned = True
        pinned_count = sum(1 for i in range(self._tabs.count())
                          if getattr(self._tabs.widget(i), '_pinned', False) and i != index)
        if index != pinned_count:
            self._tabs.tabBar().moveTab(index, pinned_count)
        bar = self._tabs.tabBar()
        bar.setTabButton(pinned_count, QTabBar.ButtonPosition.RightSide, None)
        bar.setTabButton(pinned_count, QTabBar.ButtonPosition.LeftSide, None)
        self._tabs.setTabText(pinned_count, "")
        self._tabs.setTabToolTip(pinned_count, view.title() or view.url().toString())

    def _unpin_tab(self, index):
        """Unpin a tab: restore title, move after all pinned tabs."""
        view = self._tabs.widget(index)
        if not view or not getattr(view, '_pinned', False):
            return
        view._pinned = False
        title = view.title() or "Tab"
        display = title[:30] + "\u2026" if len(title) > 30 else title
        self._tabs.setTabText(index, display)
        self._tabs.setTabToolTip(index, title)
        pinned_count = sum(1 for i in range(self._tabs.count())
                          if getattr(self._tabs.widget(i), '_pinned', False))
        if index < pinned_count:
            self._tabs.tabBar().moveTab(index, pinned_count)

    def _detach_tab(self, index):
        """Detach a tab into its own floating window, preserving the live view."""
        if self._tabs.count() <= 1:
            return
        widget = self._tabs.widget(index)
        if widget and getattr(widget, '_pinned', False):
            return

        title = self._tabs.tabText(index)
        view = self._tabs.widget(index)

        # Remove from tab bar without closing/deleting the widget
        self._tabs.removeTab(index)

        # Create a lightweight window to host the detached view
        win = QMainWindow()
        win.setWindowTitle(title)
        win.resize(900, 700)
        win.setCentralWidget(view)
        win.setStyleSheet(self.styleSheet())
        view.show()
        win.show()

        # Keep a reference so the window isn't garbage-collected
        if not hasattr(self, "_detached_windows"):
            self._detached_windows = []
        self._detached_windows.append(win)

        # Clean up reference when the window is closed
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        win.destroyed.connect(lambda: self._detached_windows.remove(win)
                              if win in self._detached_windows else None)

    def _close_other_tabs(self, keep_index):
        """Close all tabs except the one at keep_index (and pinned tabs)."""
        for i in range(self._tabs.count() - 1, -1, -1):
            if i != keep_index:
                w = self._tabs.widget(i)
                if w and getattr(w, '_pinned', False):
                    continue
                self._close_tab(i)

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def add_new_tab(self, url=None):
        view = ShroudWebView(self._profile, tab_widget=self)
        view.setZoomFactor(self._settings.get("default_zoom", 100) / 100.0)
        view.page().https_only = self._settings.get("https_only", False)

        i = self._tabs.addTab(view, "New Tab")
        self._tabs.setCurrentIndex(i)

        view.urlChanged.connect(partial(self._tab_url_changed, view))
        view.titleChanged.connect(partial(self._tab_title_changed, view))
        view.iconChanged.connect(partial(self._tab_icon_changed, view))
        view.loadStarted.connect(self._load_started)
        view.loadProgress.connect(self._load_progress)
        view.loadFinished.connect(self._load_finished)
        view.page().fullScreenRequested.connect(self._handle_fullscreen_request)
        view.page().recentlyAudibleChanged.connect(partial(self._tab_audio_changed, view))

        if url is None:
            view.load(QUrl("shroud://newtab"))
        else:
            if isinstance(url, str):
                url = QUrl(url)
            view.load(url)

        return view

    def _close_tab(self, index):
        widget = self._tabs.widget(index)
        if widget and getattr(widget, '_pinned', False):
            return
        if self._tabs.count() <= 1:
            self.close()
            return
        # Save to closed tabs stack for Ctrl+Shift+T
        url = widget.url().toString()
        title = widget.title()
        if url and not url.startswith("shroud:"):
            self._closed_tabs.append({"url": url, "title": title})
            if len(self._closed_tabs) > 20:
                self._closed_tabs = self._closed_tabs[-20:]
        self._tabs.removeTab(index)
        widget.deleteLater()

    def _close_current_tab(self):
        self._close_tab(self._tabs.currentIndex())

    def _tab_changed(self, index):
        view = self._current_view()
        if view:
            # Lazy tab loading: load deferred URL on first switch
            deferred = getattr(view, "_deferred_url", None)
            if deferred:
                view._deferred_url = None
                view.load(QUrl(deferred))
            self._update_url_bar(view.url())
            self._update_title(view.title())
            self._update_bookmark_btn(view.url())
            self._update_reader_btn()

    def _tab_url_changed(self, view, url):
        # Handle newtab search handoff: the JS sets the hash to
        # "navigate:<url>" to signal us to navigate via the URL bar,
        # avoiding Chromium's local-scheme network restrictions.
        # We must open a NEW tab because the shroud:// renderer process
        # doesn't have SOCKS proxy access.
        if url.scheme() == "shroud" and url.hasFragment():
            frag = url.fragment()
            if frag.startswith("navigate:"):
                target = frag[len("navigate:"):]
                if target:
                    idx = self._tabs.indexOf(view)
                    self.add_new_tab(QUrl(target))
                    if idx >= 0:
                        self._close_tab(idx)
                return

        if view == self._current_view():
            self._update_url_bar(url)
            self._update_bookmark_btn(url)

    def _tab_title_changed(self, view, title):
        index = self._tabs.indexOf(view)
        if index >= 0:
            if getattr(view, '_pinned', False):
                self._tabs.setTabText(index, "")
                self._tabs.setTabToolTip(index, title)
            else:
                display = title[:30] + "\u2026" if len(title) > 30 else title
                if getattr(view, '_muted', False):
                    display = "\U0001f507 " + display
                elif view.page().recentlyAudible():
                    display = "\U0001f50a " + display
                self._tabs.setTabText(index, display)
                self._tabs.setTabToolTip(index, title)
        if view == self._current_view():
            self._update_title(title)

        # Record in history (skip private mode)
        if not self._private_mode and title:
            url = view.url().toString()
            if url and not url.startswith("shroud:"):
                storage.add_history_entry(title, url)
                self._refresh_suggestions()

    def _tab_audio_changed(self, view, audible):
        """Update tab text with audio indicator."""
        index = self._tabs.indexOf(view)
        if index < 0:
            return
        if getattr(view, '_pinned', False):
            prefix = "\U0001f507 " if getattr(view, '_muted', False) else ("\U0001f50a " if audible else "")
            self._tabs.setTabToolTip(index, prefix + (view.title() or view.url().toString()))
            return
        title = view.title() or "Tab"
        display = title[:30] + "\u2026" if len(title) > 30 else title
        if getattr(view, '_muted', False):
            display = "\U0001f507 " + display
        elif audible:
            display = "\U0001f50a " + display
        self._tabs.setTabText(index, display)

    def _toggle_tab_mute(self, index):
        """Toggle mute state for the tab at the given index."""
        view = self._tabs.widget(index)
        if not view:
            return
        muted = not getattr(view, '_muted', False)
        view._muted = muted
        view.page().setAudioMuted(muted)
        self._tab_audio_changed(view, view.page().recentlyAudible())

    def _tab_icon_changed(self, view, icon):
        index = self._tabs.indexOf(view)
        if index >= 0:
            self._tabs.setTabIcon(index, icon)

    def _switch_to_tab(self, index):
        if index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    def _current_view(self):
        return self._tabs.currentWidget()

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
        if scheme == "https":
            self._security_icon.setText("\U0001f512")
            self._security_icon.setToolTip("Secure connection (HTTPS)")
            self._security_icon.setStyleSheet(f"color: {style.GREEN}; font-size: 14px; padding: 0;")
        elif scheme == "http":
            self._security_icon.setText("\u26a0")
            self._security_icon.setToolTip("Not secure (HTTP)")
            self._security_icon.setStyleSheet(f"color: {style.YELLOW}; font-size: 14px; padding: 0;")
        elif scheme == "shroud":
            self._security_icon.setText("\U0001f6e1")
            self._security_icon.setToolTip("Internal page")
            self._security_icon.setStyleSheet(f"color: {style.ACCENT}; font-size: 14px; padding: 0;")
        elif scheme == "file":
            self._security_icon.setText("\U0001f4c1")
            self._security_icon.setToolTip("Local file")
            self._security_icon.setStyleSheet(f"color: {style.TEXT_DIM}; font-size: 14px; padding: 0;")
        else:
            self._security_icon.setText("")
            self._security_icon.setToolTip("")

    def _update_title(self, title):
        suffix = "  [Private]" if self._private_mode else ""
        self.setWindowTitle(f"{title} — {__app_name__}{suffix}")

    def _focus_url_bar(self):
        self._url_bar.setFocus()
        self._url_bar.selectAll()

    # ------------------------------------------------------------------
    # URL autocomplete helpers
    # ------------------------------------------------------------------

    def _refresh_suggestions(self):
        """Reload the completer model from history + bookmarks."""
        suggestions = storage.get_url_suggestions()
        self._completer_model.clear()
        for url, title, _freq in suggestions:
            item = QStandardItem(url)
            item.setData(title, Qt.ItemDataRole.UserRole + 1)
            self._completer_model.appendRow(item)

    def _filter_completions(self, text):
        """Update the proxy filter as the user types."""
        # Don't re-filter while the user is arrowing through the popup —
        # Qt updates the line edit text as items are highlighted, which
        # would reset the model and snap the selection back to row 0.
        popup = self._url_completer.popup()
        if popup.isVisible() and popup.currentIndex().isValid():
            return
        self._completer_proxy.setFilterFixedString(text)

    def _on_completion_activated(self, index):
        """Navigate to the URL chosen from the popup."""
        url = index.data(Qt.ItemDataRole.DisplayRole)
        if url:
            self._url_bar.setText(url)
            self._current_view().load(QUrl(url))

    # ------------------------------------------------------------------
    # Loading indicators
    # ------------------------------------------------------------------

    def _load_started(self):
        self._progress.setVisible(True)
        self._progress.setValue(0)
        # Before navigating away, check if credentials were captured from a form submit
        if self._vault.is_unlocked:
            self._harvest_submitted_credentials()

    def _load_progress(self, progress):
        self._progress.setValue(progress)

    def _load_finished(self, ok):
        self._progress.setVisible(False)
        self._update_adblock_label()
        if ok:
            view = self._current_view()
            if view and getattr(view, '_reader_mode_active', False):
                pass  # Reader mode page — skip content injection
            elif view and not view.url().toString().startswith("shroud:"):
                # Inject cosmetic CSS (ad hiding + cookie banners)
                if self._cosmetic_css and self._settings.get("enable_adblock", True):
                    css_js = "var s=document.createElement('style');" \
                             "s.id='shroud-cosmetic-css';" \
                             "s.textContent=" + json.dumps(self._cosmetic_css) + ";" \
                             "document.head.appendChild(s);"
                    view.page().runJavaScript(css_js)
                # Inject dynamic cosmetic observer + script blocker
                if self._settings.get("enable_adblock", True):
                    view.page().runJavaScript(self._get_content_blocking_js())
                # Inject fingerprint resistance
                if self._settings.get("fingerprint_resistance", False):
                    view.page().runJavaScript(get_fingerprint_resistance_js())
            if self._vault.is_unlocked:
                self._check_page_for_passwords()
            # Give the web view keyboard focus on new-tab so typing
            # reaches the page's keydown listener immediately.
            if view and view.url().scheme() == "shroud" and view.url().host() == "newtab":
                view.setFocus()

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

            // Observe DOM for dynamically added ads and scripts
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
                if (needsHide) hideAdElements();
            });
            observer.observe(document.documentElement, {childList: true, subtree: true});
        })();"""

    def _hard_reload(self):
        """Reload bypassing cache."""
        view = self._current_view()
        if view:
            view.triggerPageAction(view.page().WebAction.ReloadAndBypassCache)

    def _update_adblock_label(self):
        if self._adblocker.enabled:
            count = self._adblocker.blocked_count
            self._adblock_label.setText(f"  {count} blocked")
            self._adblock_label.setStyleSheet(style.ADBLOCK_LABEL_ON_STYLE)
        else:
            self._adblock_label.setText("  shield off")
            self._adblock_label.setStyleSheet(style.ADBLOCK_LABEL_OFF_STYLE)

    # ------------------------------------------------------------------
    # Bookmarks
    # ------------------------------------------------------------------

    def _toggle_bookmark(self):
        view = self._current_view()
        if not view:
            return
        url = view.url().toString()
        title = view.title()

        if storage.is_bookmarked(url):
            storage.remove_bookmark(url)
            self._bookmark_btn.setText("\u2606")
            self._status.showMessage("Bookmark removed", 2000)
        else:
            storage.add_bookmark(title, url)
            self._bookmark_btn.setText("\u2605")
            self._status.showMessage("Bookmark added", 2000)

        self._populate_bookmarks_menu()

    def _update_bookmark_btn(self, url):
        if storage.is_bookmarked(url.toString()):
            self._bookmark_btn.setText("\u2605")
        else:
            self._bookmark_btn.setText("\u2606")

    def _populate_bookmarks_menu(self):
        actions = self._bookmarks_menu.actions()
        for a in actions[6:]:
            self._bookmarks_menu.removeAction(a)

        for bm in storage.load_bookmarks()[:20]:
            label = bm["title"][:40] or bm["url"][:40]
            action = self._bookmarks_menu.addAction(label)
            action.setData(bm["url"])
            action.triggered.connect(partial(self._open_bookmark, bm["url"]))

    def _open_bookmark(self, url):
        self._current_view().load(QUrl(url))

    def _show_bookmarks(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Bookmarks")
        dialog.setMinimumSize(520, 440)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        listw = QListWidget()
        listw.setStyleSheet(style.LIST_WIDGET_STYLE)

        bookmarks = storage.load_bookmarks()
        for bm in bookmarks:
            item = QListWidgetItem(f'{bm["title"]}\n{bm["url"]}')
            item.setData(Qt.ItemDataRole.UserRole, bm["url"])
            listw.addItem(item)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        open_btn = QPushButton("Open")
        open_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        def open_selected():
            item = listw.currentItem()
            if item:
                self._current_view().load(QUrl(item.data(Qt.ItemDataRole.UserRole)))
                dialog.close()

        def delete_selected():
            item = listw.currentItem()
            if item:
                storage.remove_bookmark(item.data(Qt.ItemDataRole.UserRole))
                listw.takeItem(listw.row(item))
                self._populate_bookmarks_menu()
                self._update_bookmark_btn(self._current_view().url())

        open_btn.clicked.connect(open_selected)
        delete_btn.clicked.connect(delete_selected)
        close_btn.clicked.connect(dialog.close)
        listw.itemDoubleClicked.connect(lambda: open_selected())

        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addWidget(listw)
        layout.addLayout(btn_layout)
        dialog.exec()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Browsing History")
        dialog.setMinimumSize(580, 480)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        search = QLineEdit()
        search.setPlaceholderText("  Filter history...")
        search.setStyleSheet(style.SEARCH_INPUT_STYLE)
        layout.addWidget(search)

        listw = QListWidget()
        listw.setStyleSheet(style.LIST_WIDGET_STYLE)

        history = storage.load_history()

        def populate(filter_text=""):
            listw.clear()
            ft = filter_text.lower()
            for h in history:
                if ft and ft not in h["title"].lower() and ft not in h["url"].lower():
                    continue
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(h["visited"]))
                item = QListWidgetItem(f'[{ts}]  {h["title"]}\n{h["url"]}')
                item.setData(Qt.ItemDataRole.UserRole, h["url"])
                listw.addItem(item)

        populate()
        search.textChanged.connect(populate)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        open_btn = QPushButton("Open")
        open_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        def open_selected():
            item = listw.currentItem()
            if item:
                self._current_view().load(QUrl(item.data(Qt.ItemDataRole.UserRole)))
                dialog.close()

        open_btn.clicked.connect(open_selected)
        close_btn.clicked.connect(dialog.close)
        listw.itemDoubleClicked.connect(lambda: open_selected())

        btn_layout.addWidget(open_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addWidget(listw)
        layout.addLayout(btn_layout)
        dialog.exec()

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all browsing history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            storage.clear_history()
            self._status.showMessage("History cleared", 2000)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def _show_downloads(self):
        self._download_shelf.toggle()

    # ------------------------------------------------------------------
    # Print / Save as PDF
    # ------------------------------------------------------------------

    def _print_page(self):
        view = self._current_view()
        if not view:
            return
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            def _on_print_done(success):
                if success:
                    self._status.showMessage("Page printed", 3000)
                else:
                    self._status.showMessage("Printing failed", 3000)
            view.page().print(printer, _on_print_done)

    def _save_pdf(self):
        view = self._current_view()
        if not view:
            return
        title = view.title() or "page"
        # Sanitise the title for use as a default filename
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save as PDF", f"{safe}.pdf", "PDF files (*.pdf)"
        )
        if path:
            page = view.page()
            page.pdfPrintingFinished.connect(self._on_pdf_saved)
            page.printToPdf(path)

    def _on_pdf_saved(self, file_path, success):
        # Disconnect to avoid duplicate signals from future saves
        page = self.sender()
        if page:
            page.pdfPrintingFinished.disconnect(self._on_pdf_saved)
        if success:
            self._status.showMessage(f"PDF saved to {file_path}", 4000)
        else:
            self._status.showMessage("PDF save failed", 3000)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def _zoom_in(self):
        view = self._current_view()
        if view:
            view.setZoomFactor(min(view.zoomFactor() + 0.1, 5.0))

    def _zoom_out(self):
        view = self._current_view()
        if view:
            view.setZoomFactor(max(view.zoomFactor() - 0.1, 0.25))

    def _zoom_reset(self):
        view = self._current_view()
        if view:
            view.setZoomFactor(1.0)

    # ------------------------------------------------------------------
    # Full screen
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        self._navbar.hide()
        self._tabs.tabBar().hide()
        self._status.hide()
        self.showFullScreen()

    def _exit_fullscreen(self):
        self._navbar.show()
        self._tabs.tabBar().show()
        self._status.show()
        self.showNormal()

    def _handle_fullscreen_request(self, request):
        request.accept()
        if request.toggleOn():
            self._enter_fullscreen()
        else:
            self._exit_fullscreen()

    def _prompt_http_auth(self, url):
        """Show a non-blocking auth dialog for an HTTP 401 protected URL.

        Called from ShroudPage.acceptNavigationRequest when a HEAD probe
        detects that the server requires authentication.  Chromium 134
        crashes (SIGTRAP) on any 401 response, and setHttpHeader for
        Authorization is silently stripped.  So we fetch the page with
        Python's urllib and inject the HTML via setHtml().
        """
        host = (url.host() or "").lower()

        # Guard against duplicate dialogs
        pending = getattr(self, "_http_auth_pending", set())
        if host in pending:
            return
        if not hasattr(self, "_http_auth_pending"):
            self._http_auth_pending = set()
        self._http_auth_pending.add(host)

        url_copy = QUrl(url)
        dlg = HttpAuthDialog(host or url.toString(), "", parent=self)
        dlg.setModal(True)

        def on_finished(result):
            self._http_auth_pending.discard(host)
            if result != QDialog.DialogCode.Accepted.value:
                return
            user, pw = dlg.credentials()
            # Store creds so the interceptor can handle sub-resources
            self._adblocker.set_http_auth(host, user, pw)
            # Fetch the page with Python — Chromium must never see a 401
            self._fetch_authed_page(url_copy, host, user, pw)

        dlg.finished.connect(on_finished)
        dlg.show()

    def _fetch_authed_page(self, url, host, user, pw):
        """Fetch a page using Python with Basic auth, inject via setHtml."""
        import base64
        import ssl
        import urllib.request

        url_string = url.toString()
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        req = urllib.request.Request(url_string)
        req.add_header("Authorization", f"Basic {token}")
        req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/134.0.0.0 Safari/537.36")
        ctx = ssl.create_default_context()
        try:
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            html = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            view = self._current_view()
            if view:
                # setHtml with baseUrl so relative resources resolve correctly
                view.page().setHtml(
                    html.decode(charset, errors="replace"), url)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # Wrong credentials — clear cached auth and re-prompt
                self._adblocker.clear_http_auth(host)
                self._prompt_http_auth(url)
            else:
                self._status.showMessage(
                    f"HTTP error {e.code} loading {host}", 5000)
        except Exception as e:
            self._status.showMessage(
                f"Failed to load {host}: {e}", 5000)

    # ------------------------------------------------------------------
    # Dev tools & view source
    # ------------------------------------------------------------------

    def _open_devtools(self):
        view = self._current_view()
        if not view:
            return
        devtools = ShroudWebView(self._profile, tab_widget=self)
        view.page().setDevToolsPage(devtools.page())
        i = self._tabs.addTab(devtools, "DevTools")
        self._tabs.setCurrentIndex(i)

    def _view_source(self):
        view = self._current_view()
        if view:
            view.page().toHtml(self._show_source_dialog)

    def _show_source_dialog(self, html):
        dialog = QDialog(self)
        dialog.setWindowTitle("Page Source")
        dialog.setMinimumSize(720, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        from PyQt6.QtWidgets import QTextEdit
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(html)
        editor.setStyleSheet(style.SOURCE_EDITOR_STYLE)
        layout.addWidget(editor)
        dialog.exec()

    # ------------------------------------------------------------------
    # Find on page (enhanced find bar)
    # ------------------------------------------------------------------

    def _create_find_bar(self):
        bar = QFrame()
        bar.setStyleSheet(style.FIND_BAR_STYLE)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Find on page...")
        self._find_input.returnPressed.connect(self._find_next)
        self._find_input.textChanged.connect(self._on_find_text_changed)

        prev_btn = QPushButton("\u25B2")
        prev_btn.setToolTip("Previous (Shift+Enter)")
        prev_btn.setStyleSheet(style.FIND_BAR_BTN_STYLE)
        prev_btn.clicked.connect(self._find_prev)

        next_btn = QPushButton("\u25BC")
        next_btn.setToolTip("Next (Enter)")
        next_btn.setStyleSheet(style.FIND_BAR_BTN_STYLE)
        next_btn.clicked.connect(self._find_next)

        self._find_count_label = QLabel("")

        self._find_case_check = QCheckBox("Match case")

        close_btn = QPushButton("\u2715")
        close_btn.setToolTip("Close (Escape)")
        close_btn.setStyleSheet(style.FIND_BAR_BTN_STYLE)
        close_btn.clicked.connect(self._close_find_bar)

        layout.addWidget(self._find_input)
        layout.addWidget(prev_btn)
        layout.addWidget(next_btn)
        layout.addWidget(self._find_count_label)
        layout.addWidget(self._find_case_check)
        layout.addStretch()
        layout.addWidget(close_btn)
        return bar

    def _find_on_page(self):
        self._find_bar.setVisible(True)
        self._find_input.setFocus()
        self._find_input.selectAll()

    def _close_find_bar(self):
        self._find_bar.setVisible(False)
        self._find_count_label.setText("")
        view = self._current_view()
        if view:
            view.findText("")  # clear highlights

    def _find_flags(self, backward=False):
        flags = QWebEnginePage.FindFlag(0)
        if self._find_case_check.isChecked():
            flags |= QWebEnginePage.FindFlag.FindCaseSensitively
        if backward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        return flags

    def _on_find_text_changed(self, text):
        if text:
            self._do_find(text, self._find_flags())
        else:
            self._current_view().findText("")
            self._find_count_label.setText("")

    def _find_next(self):
        text = self._find_input.text()
        if text:
            self._do_find(text, self._find_flags())

    def _find_prev(self):
        text = self._find_input.text()
        if text:
            self._do_find(text, self._find_flags(backward=True))

    def _do_find(self, text, flags):
        view = self._current_view()
        if not view:
            return
        view.findText(text, flags, self._on_find_result)

    def _on_find_result(self, result):
        if hasattr(result, "numberOfMatches"):
            active = result.activeMatch()
            total = result.numberOfMatches()
            if total > 0:
                self._find_count_label.setText(f"{active} of {total}")
            else:
                self._find_count_label.setText("No matches")
        # Older Qt versions may not have this — just leave blank

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    def _open_new_window(self):
        win = MainWindow()
        win.show()

    def _open_private_window(self):
        old_setting = self._settings.get("private_mode", False)
        self._settings["private_mode"] = True
        win = MainWindow()
        win.show()
        self._settings["private_mode"] = old_setting

    def _reopen_closed_tab(self):
        if not self._closed_tabs:
            self._status.showMessage("No recently closed tabs", 2000)
            return
        tab_info = self._closed_tabs.pop()
        self.add_new_tab(tab_info["url"])

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def _show_settings(self):
        from PyQt6.QtWidgets import QScrollArea

        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setMinimumWidth(520)
        dialog.setStyleSheet(style.SETTINGS_FORM_STYLE)

        # Outer layout holds the scroll area and bottom buttons
        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {style.BG_MID}; border: none; }}")

        form_widget = QWidget()
        layout = QFormLayout(form_widget)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        search_edit = QLineEdit(self._settings.get("search_engine", ""))
        search_edit.setToolTip("Use {} as placeholder for the search query")

        js_check = QCheckBox("Enabled")
        js_check.setChecked(self._settings.get("enable_javascript", True))

        adblock_check = QCheckBox("Enabled")
        adblock_check.setChecked(self._settings.get("enable_adblock", True))

        zoom_spin = QSpinBox()
        zoom_spin.setRange(25, 500)
        zoom_spin.setSuffix(" %")
        zoom_spin.setValue(self._settings.get("default_zoom", 100))

        ua_edit = QLineEdit(self._settings.get("user_agent", ""))
        ua_edit.setPlaceholderText("Leave blank for default")

        https_check = QCheckBox("Enabled")
        https_check.setChecked(self._settings.get("https_only", False))

        dnt_check = QCheckBox("Enabled")
        dnt_check.setChecked(self._settings.get("do_not_track", True))

        session_check = QCheckBox("Enabled")
        session_check.setChecked(self._settings.get("restore_session", True))

        strip_check = QCheckBox("Enabled")
        strip_check.setChecked(self._settings.get("strip_tracking", True))

        fp_check = QCheckBox("Enabled")
        fp_check.setChecked(self._settings.get("fingerprint_resistance", False))

        from PyQt6.QtWidgets import QComboBox
        doh_combo = QComboBox()
        doh_combo.addItems(["off", "automatic", "secure"])
        doh_combo.setCurrentText(self._settings.get("dns_over_https", "automatic"))
        doh_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 12px; background: {style.BG_DARK}; color: {style.TEXT};
                border: 2px solid {style.BORDER}; border-radius: 8px; font-size: 13px;
            }}
            QComboBox:focus {{ border-color: {style.ACCENT}; }}
            QComboBox QAbstractItemView {{
                background: {style.BG_CARD}; color: {style.TEXT};
                border: 1px solid {style.BORDER}; selection-background-color: {style.ACCENT};
            }}
        """)

        layout.addRow("Search Engine", search_edit)
        layout.addRow("JavaScript", js_check)
        layout.addRow("Ad Blocker", adblock_check)
        layout.addRow("Default Zoom", zoom_spin)
        layout.addRow("User Agent", ua_edit)
        layout.addRow("HTTPS-Only Mode", https_check)
        layout.addRow("Do Not Track", dnt_check)
        layout.addRow("Strip Tracking Params", strip_check)
        layout.addRow("Fingerprint Resistance", fp_check)
        layout.addRow("DNS-over-HTTPS", doh_combo)

        doh_provider_edit = QLineEdit(self._settings.get(
            "dns_over_https_provider", "https://dns.cloudflare.com/dns-query"))
        doh_provider_edit.setPlaceholderText("https://dns.cloudflare.com/dns-query")
        doh_provider_edit.setToolTip("DoH server URL (e.g. your pfSense Unbound endpoint)")
        layout.addRow("DoH Provider URL", doh_provider_edit)

        doh_note = QLabel("DNS-over-HTTPS changes require a browser restart.")
        doh_note.setStyleSheet(f"color: {style.TEXT_FAINT}; font-size: 11px;")
        layout.addRow("", doh_note)

        layout.addRow("Restore Session", session_check)

        # --- Shroud DNS section ---
        dns_separator = QLabel("── Shroud DNS ──")
        dns_separator.setStyleSheet(f"color: {style.TEXT_DIM}; font-size: 12px;")
        dns_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addRow(dns_separator)

        custom_dns_server = QLineEdit(self._settings.get("custom_dns_server", ""))
        custom_dns_server.setPlaceholderText("https://pfsense.local:8853")
        custom_dns_server.setToolTip("Base URL of your Shroud DNS server")

        # Registration state tracking (in-dialog, persisted on Save)
        _reg_secret = [storage.get_dns_secret(self._settings)]
        _reg_fingerprint = [storage.get_dns_cert_fingerprint(self._settings)]

        is_registered = bool(_reg_secret[0])
        dns_status_label = QLabel(
            "Registered" if is_registered else "Not registered"
        )
        dns_status_label.setStyleSheet(
            f"color: {'#4caf50' if is_registered else style.TEXT_FAINT}; font-size: 11px;"
        )

        register_btn = QPushButton()
        register_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        def _update_reg_ui():
            registered = bool(_reg_secret[0])
            register_btn.setText("Unregister" if registered else "Register")
            dns_status_label.setText("Registered" if registered else "Not registered")
            dns_status_label.setStyleSheet(
                f"color: {'#4caf50' if registered else style.TEXT_FAINT}; font-size: 11px;"
            )
            custom_dns_server.setReadOnly(registered)

        _update_reg_ui()

        def _do_register():
            # If already registered, unregister instead
            if _reg_secret[0]:
                confirm = QMessageBox.question(
                    dialog, "Shroud DNS",
                    "Unregistering will clear your DNS credentials "
                    "and restart the browser.\n\nContinue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
                # Clear credentials from keyring and settings
                storage.clear_dns_secrets(self._settings)
                self._settings["custom_dns_enabled"] = False
                self._settings["custom_dns_server"] = ""
                storage.save_settings(self._settings)
                dialog.reject()
                # Restart the browser
                self._restart_browser()
                return

            url = custom_dns_server.text().strip()
            if not url:
                QMessageBox.warning(dialog, "Shroud DNS", "Enter a server URL first.")
                return
            # Normalize: strip trailing slash and path
            base = url.rstrip("/")
            for suffix in ("/shroud-dns-query", "/shroud-dns-register", "/health"):
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
                    break
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                import http.client
                import json as _json
                import ssl as _ssl
                import urllib.parse
                parsed = urllib.parse.urlparse(base)
                ctx = _ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
                conn = http.client.HTTPSConnection(
                    parsed.hostname, parsed.port or 443,
                    context=ctx, timeout=10,
                )
                conn.connect()
                conn.request("GET", "/shroud-dns-register")
                resp = conn.getresponse()
                if resp.status != 200:
                    raise RuntimeError(f"Server returned HTTP {resp.status}")
                data = _json.loads(resp.read())
                conn.close()

                # Save credentials to OS keyring (raises if unavailable)
                secret = data["secret"]
                fingerprint = data.get("cert_fingerprint", "")
                storage.save_dns_secrets(self._settings, secret, fingerprint)
                self._settings["custom_dns_enabled"] = True
                self._settings["custom_dns_server"] = base
                storage.save_settings(self._settings)
                QApplication.restoreOverrideCursor()
                dialog.reject()
                self._restart_browser()
                return
            except Exception as exc:
                QMessageBox.critical(
                    dialog, "Shroud DNS",
                    f"Registration failed:\n{exc}"
                )
            finally:
                QApplication.restoreOverrideCursor()

        register_btn.clicked.connect(_do_register)

        # URL row with register button
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        url_row.addWidget(custom_dns_server, 1)
        url_row.addWidget(register_btn)
        url_container = QWidget()
        url_container.setLayout(url_row)

        custom_dns_fallback = QCheckBox("Fall back to system DNS if server unreachable")
        custom_dns_fallback.setChecked(self._settings.get("custom_dns_fallback", True))

        layout.addRow("Server", url_container)
        layout.addRow("Status", dns_status_label)
        layout.addRow("", custom_dns_fallback)

        custom_dns_note = QLabel(
            "Enter your server URL and click Register.\n"
            "When registered, overrides DNS-over-HTTPS above.\n"
            "Clear the URL and save to disable. Requires restart."
        )
        custom_dns_note.setStyleSheet(f"color: {style.TEXT_FAINT}; font-size: 11px;")
        layout.addRow("", custom_dns_note)

        # Grey out DoH fields when Shroud DNS is registered
        def _toggle_dns_sections():
            registered = bool(_reg_secret[0])
            doh_combo.setEnabled(not registered)
            doh_provider_edit.setEnabled(not registered)

        _toggle_dns_sections()

        scroll.setWidget(form_widget)
        outer_layout.addWidget(scroll, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(24, 12, 24, 16)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        save_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        outer_layout.addLayout(btn_layout)

        # Size to content but cap at 80% of screen height so it scrolls on small screens
        screen = self.screen()
        if screen:
            max_h = int(screen.availableGeometry().height() * 0.8)
            dialog.resize(dialog.sizeHint().width(), min(dialog.sizeHint().height(), max_h))

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._settings["search_engine"] = search_edit.text()
            self._settings["enable_javascript"] = js_check.isChecked()
            self._settings["enable_adblock"] = adblock_check.isChecked()
            self._settings["default_zoom"] = zoom_spin.value()
            self._settings["user_agent"] = ua_edit.text()
            self._settings["https_only"] = https_check.isChecked()
            self._settings["do_not_track"] = dnt_check.isChecked()
            self._settings["restore_session"] = session_check.isChecked()
            self._settings["strip_tracking"] = strip_check.isChecked()
            self._settings["fingerprint_resistance"] = fp_check.isChecked()
            self._settings["dns_over_https"] = doh_combo.currentText()
            self._settings["dns_over_https_provider"] = doh_provider_edit.text().strip()
            server_url = custom_dns_server.text().strip()
            secret = _reg_secret[0]
            fingerprint = _reg_fingerprint[0]
            # Auto-enable when registered, auto-disable when URL cleared
            self._settings["custom_dns_enabled"] = bool(server_url and secret)
            self._settings["custom_dns_server"] = server_url
            self._settings["custom_dns_fallback"] = custom_dns_fallback.isChecked()
            if secret:
                storage.save_dns_secrets(self._settings, secret, fingerprint)
            else:
                storage.clear_dns_secrets(self._settings)
            storage.save_settings(self._settings)

            # Update proxy config at runtime if it's running
            if self._dns_proxy is not None:
                _base = self._settings["custom_dns_server"].rstrip("/")
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
                view = self._tabs.widget(i)
                if view and hasattr(view.page(), "https_only"):
                    view.page().https_only = self._settings["https_only"]

            # Apply DNT
            self._adblocker.do_not_track = self._settings["do_not_track"]

            self._status.showMessage("Settings saved", 2000)

    # ------------------------------------------------------------------
    # Password manager
    # ------------------------------------------------------------------

    def _ensure_vault_unlocked(self) -> bool:
        """Prompt for master password if needed. Returns True if vault is unlocked."""
        if self._vault.is_unlocked:
            return True

        from . import keyring_backend

        # Keyring backend — try auto-unlock, no dialog needed
        if self._settings.get("vault_backend") == "keyring":
            if self._vault.unlock_with_keyring():
                return True
            QMessageBox.warning(
                self, "Password Vault",
                "Could not access OS keyring.\n"
                "You may need to unlock your login keyring."
            )
            return False

        # No vault exists yet — auto-create with keyring if available
        if not self._vault.is_setup() and keyring_backend.is_available():
            try:
                self._vault.setup_with_keyring()
                self._settings["vault_backend"] = "keyring"
                storage.save_settings(self._settings)
                return True
            except Exception:
                pass  # Fall through to master password dialog

        dlg = MasterPasswordDialog(
            self._vault, parent=self,
            keyring_available=keyring_backend.is_available(),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Save chosen backend on first setup
            if dlg.chosen_backend != self._settings.get("vault_backend", "master_password"):
                self._settings["vault_backend"] = dlg.chosen_backend
                storage.save_settings(self._settings)
            return True
        return False

    def _show_password_manager(self):
        if not self._ensure_vault_unlocked():
            return
        dlg = PasswordManagerDialog(self._vault, parent=self)
        dlg.exec()

    def _auto_fill_password(self):
        """Fill credentials into the current page's login form."""
        view = self._current_view()
        if not view:
            return
        if not self._ensure_vault_unlocked():
            return
        url = view.url().toString()
        entries = self._vault.get_entries_for_url(url)
        if not entries:
            self._status.showMessage("No saved passwords for this site", 3000)
            return
        # Use the most recently used entry, or first one
        entry = max(entries, key=lambda e: e.get("last_used", 0))
        self._vault.touch_entry(entry["id"])
        username = entry["username"].replace("\\", "\\\\").replace("'", "\\'")
        password = entry["password"].replace("\\", "\\\\").replace("'", "\\'")
        js = f"""
        (function() {{
            var filled = false;
            var inputs = document.querySelectorAll('input');
            var pwFields = [];
            var userFields = [];
            inputs.forEach(function(input) {{
                if (input.type === 'password' && input.offsetParent !== null) {{
                    pwFields.push(input);
                }}
            }});
            if (pwFields.length > 0) {{
                // Find username field: look for text/email input before the password field
                var allInputs = Array.from(document.querySelectorAll('input'));
                var pwIdx = allInputs.indexOf(pwFields[0]);
                for (var i = pwIdx - 1; i >= 0; i--) {{
                    var t = allInputs[i].type;
                    if ((t === 'text' || t === 'email' || t === '') && allInputs[i].offsetParent !== null) {{
                        userFields.push(allInputs[i]);
                        break;
                    }}
                }}
                if (userFields.length > 0) {{
                    var nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeSet.call(userFields[0], '{username}');
                    userFields[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                    userFields[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
                var nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSet.call(pwFields[0], '{password}');
                pwFields[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                pwFields[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                filled = true;
            }}
            return filled;
        }})();
        """
        view.page().runJavaScript(js, self._on_autofill_result)

    def _on_autofill_result(self, filled):
        if filled:
            self._status.showMessage("Password auto-filled", 2000)
        else:
            self._status.showMessage("No login form found on this page", 3000)

    def _check_page_for_passwords(self):
        """After page load, detect login forms: notify for autofill and inject submit interceptor."""
        view = self._current_view()
        if not view:
            return
        url = view.url().toString()
        if url.startswith("shroud:"):
            return
        # Inject JS that:
        # 1. Counts visible password fields
        # 2. Installs a submit interceptor to capture credentials
        js = """
        (function() {
            var pwInputs = document.querySelectorAll('input[type="password"]');
            var visible = 0;
            pwInputs.forEach(function(i) { if (i.offsetParent !== null) visible++; });

            if (visible > 0 && !window.__shroudPasswordHooked) {
                window.__shroudPasswordHooked = true;
                window.__shroudCapturedCreds = null;

                document.addEventListener('submit', function(e) {
                    var form = e.target;
                    var pw = form.querySelector('input[type="password"]');
                    if (!pw || !pw.value) return;

                    // Find username field: closest text/email input before the password
                    var inputs = Array.from(form.querySelectorAll('input'));
                    var pwIdx = inputs.indexOf(pw);
                    var username = '';
                    for (var i = pwIdx - 1; i >= 0; i--) {
                        var t = inputs[i].type;
                        if ((t === 'text' || t === 'email' || t === '') && inputs[i].value) {
                            username = inputs[i].value;
                            break;
                        }
                    }
                    window.__shroudCapturedCreds = {
                        username: username,
                        password: pw.value,
                        url: window.location.href
                    };
                }, true);

                // Also catch clicks on submit buttons outside <form> (SPA login flows)
                document.addEventListener('click', function(e) {
                    var btn = e.target.closest('button[type="submit"], input[type="submit"]');
                    if (!btn) return;
                    var form = btn.closest('form');
                    if (form) return;  // handled by submit event above

                    // Look for a nearby password field
                    var pwAll = document.querySelectorAll('input[type="password"]');
                    pwAll.forEach(function(pw) {
                        if (!pw.value) return;
                        var container = pw.closest('div, section, main, body');
                        if (!container) return;
                        var inputs = Array.from(container.querySelectorAll('input'));
                        var pwIdx = inputs.indexOf(pw);
                        var username = '';
                        for (var i = pwIdx - 1; i >= 0; i--) {
                            var t = inputs[i].type;
                            if ((t === 'text' || t === 'email' || t === '') && inputs[i].value) {
                                username = inputs[i].value;
                                break;
                            }
                        }
                        if (pw.value) {
                            window.__shroudCapturedCreds = {
                                username: username,
                                password: pw.value,
                                url: window.location.href
                            };
                        }
                    });
                }, true);
            }
            return visible;
        })();
        """
        view.page().runJavaScript(js, lambda count: self._on_password_fields_detected(count, url))

    def _on_password_fields_detected(self, count, url):
        if not count or count <= 0:
            return
        entries = self._vault.get_entries_for_url(url)
        if entries:
            self._status.showMessage(
                "Saved password available \u2014 press Ctrl+Shift+L to auto-fill", 5000
            )

    def _harvest_submitted_credentials(self):
        """Read credentials captured by the form submit interceptor."""
        view = self._current_view()
        if not view:
            return
        js = """
        (function() {
            var c = window.__shroudCapturedCreds;
            window.__shroudCapturedCreds = null;
            return c;
        })();
        """
        view.page().runJavaScript(js, self._on_credentials_harvested)

    def _on_credentials_harvested(self, creds):
        if not creds or not isinstance(creds, dict):
            return
        username = creds.get("username", "")
        password = creds.get("password", "")
        url = creds.get("url", "")
        if not password or not url:
            return

        # Don't offer to save if we already have this exact credential
        existing = self._vault.get_entries_for_url(url)
        for e in existing:
            if e["username"] == username and e["password"] == password:
                return

        from urllib.parse import urlparse
        domain = urlparse(url).hostname or url

        # Remove any previous save bar
        if self._password_save_bar:
            self._password_save_bar._remove()
            self._password_save_bar = None

        def on_save():
            if not self._vault.is_unlocked:
                return
            # Update existing entry for same user, or add new
            for e in existing:
                if e["username"] == username:
                    self._vault.update_entry(e["id"], password=password)
                    self._status.showMessage("Password updated", 3000)
                    self._password_save_bar = None
                    return
            self._vault.add_entry(url, username, password, domain)
            self._status.showMessage("Password saved", 3000)
            self._password_save_bar = None

        def on_dismiss():
            self._password_save_bar = None

        bar = PasswordSaveBar(domain, username or "(no username)", on_save, on_dismiss, parent=self)
        self._password_save_bar = bar

        # Insert bar at top of the central layout (above tabs)
        self._central_layout.insertWidget(0, bar)

    # ------------------------------------------------------------------
    # Filter lists manager
    # ------------------------------------------------------------------

    def _show_filter_lists(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Filter Lists")
        dialog.setMinimumSize(560, 480)
        dialog.setStyleSheet(style.FILTER_LIST_STYLE)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        info_label = QLabel(f"Blocked domains: {self._adblocker.total_rules:,}")
        info_label.setStyleSheet(f"color: {style.GREEN}; font-size: 14px; font-weight: 600;")
        layout.addWidget(info_label)

        settings = filterlists.load_list_settings()
        checkboxes = {}
        status_labels = {}

        from PyQt6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)

        for fl in filterlists.FILTER_LISTS:
            cb = QCheckBox(fl["name"])
            cb.setChecked(settings.get(fl["id"], fl["enabled_default"]))
            desc = QLabel(fl["description"])
            desc.setStyleSheet(f"color: {style.TEXT_DIM}; font-size: 12px; margin-left: 26px;")
            desc.setWordWrap(True)

            cached = filterlists.is_cached(fl["id"])
            status = QLabel("Downloaded" if cached else "Not downloaded")
            status.setStyleSheet(
                f"color: {style.GREEN if cached else style.TEXT_FAINT}; font-size: 11px; margin-left: 26px;"
            )

            scroll_layout.addWidget(cb)
            scroll_layout.addWidget(desc)
            scroll_layout.addWidget(status)
            checkboxes[fl["id"]] = cb
            status_labels[fl["id"]] = status

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        enable_all = QPushButton("Enable All")
        enable_all.setStyleSheet(style.DIALOG_BTN_STYLE)
        enable_all.clicked.connect(lambda: [cb.setChecked(True) for cb in checkboxes.values()])

        disable_all = QPushButton("Disable All")
        disable_all.setStyleSheet(style.DIALOG_BTN_STYLE)
        disable_all.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxes.values()])

        update_btn = QPushButton("Update Lists")
        update_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        close_btn.clicked.connect(dialog.close)

        def save_and_update():
            import queue
            import threading
            from PyQt6.QtCore import QTimer

            new_settings = {fid: cb.isChecked() for fid, cb in checkboxes.items()}
            filterlists.save_list_settings(new_settings)
            update_btn.setText("Downloading...")
            update_btn.setEnabled(False)

            # Mark enabled lists as downloading
            for fid, lbl in status_labels.items():
                if new_settings.get(fid, False):
                    lbl.setText("Downloading...")
                    lbl.setStyleSheet(f"color: {style.TEXT_DIM}; font-size: 11px; margin-left: 26px;")

            progress_q = queue.Queue()

            def _on_item(list_id, success):
                progress_q.put((list_id, success))

            t = threading.Thread(
                target=filterlists.download_all_enabled,
                args=(_on_item,), daemon=True,
            )
            t.start()

            poll = QTimer(dialog)

            def _check():
                # Drain progress updates
                while not progress_q.empty():
                    list_id, success = progress_q.get_nowait()
                    lbl = status_labels.get(list_id)
                    if lbl:
                        lbl.setText("Updated" if success else "Failed")
                        lbl.setStyleSheet(
                            f"color: {style.GREEN if success else style.RED}; "
                            f"font-size: 11px; margin-left: 26px;"
                        )

                if t.is_alive():
                    return
                poll.stop()
                self._adblocker.reload_hosts()
                self._cosmetic_css = filterlists.get_cosmetic_css()
                info_label.setText(f"Blocked domains: {self._adblocker.total_rules:,}")
                update_btn.setText("Update Lists")
                update_btn.setEnabled(True)
                self._update_adblock_label()
                self._status.showMessage(
                    f"Filter lists updated — {self._adblocker.total_rules:,} domains blocked", 4000
                )

            poll.timeout.connect(_check)
            poll.start(200)

        def save_settings():
            new_settings = {fid: cb.isChecked() for fid, cb in checkboxes.items()}
            filterlists.save_list_settings(new_settings)
            self._adblocker.reload_hosts()
            self._cosmetic_css = filterlists.get_cosmetic_css()
            info_label.setText(f"Blocked domains: {self._adblocker.total_rules:,}")

        update_btn.clicked.connect(save_and_update)
        # Save checkbox state when toggled
        for cb in checkboxes.values():
            cb.toggled.connect(lambda _: save_settings())

        btn_layout.addWidget(enable_all)
        btn_layout.addWidget(disable_all)
        btn_layout.addStretch()
        btn_layout.addWidget(update_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def _show_about(self):
        self.add_new_tab(QUrl("shroud://about"))

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def _take_screenshot(self):
        view = self._current_view()
        if not view:
            return
        pixmap = view.grab()
        title = view.title() or "screenshot"
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", f"{safe}.png",
            "PNG images (*.png);;JPEG images (*.jpg);;All files (*)")
        if path:
            pixmap.save(path)
            self._status.showMessage(f"Screenshot saved to {path}", 4000)

    # ------------------------------------------------------------------
    # Picture in Picture
    # ------------------------------------------------------------------

    def _toggle_pip(self):
        view = self._current_view()
        if view:
            view.page().runJavaScript("""
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
            """)

    # ------------------------------------------------------------------
    # Bookmark import / export
    # ------------------------------------------------------------------

    def _export_bookmarks(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Bookmarks", "bookmarks.html", "HTML files (*.html)")
        if not path:
            return
        bookmarks = storage.load_bookmarks()
        lines = [
            '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            '<TITLE>Bookmarks</TITLE>',
            '<H1>Bookmarks</H1>',
            '<DL><p>',
        ]
        for bm in bookmarks:
            ts = int(bm.get("added", time.time()))
            title = html_mod.escape(bm["title"])
            url = html_mod.escape(bm["url"])
            lines.append(f'    <DT><A HREF="{url}" ADD_DATE="{ts}">{title}</A>')
        lines.append('</DL><p>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        self._status.showMessage(f"Exported {len(bookmarks)} bookmarks", 3000)

    def _import_bookmarks(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Bookmarks", "", "HTML files (*.html);;All files (*)")
        if not path:
            return
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        pattern = r'<A\s+HREF="([^"]+)"[^>]*>([^<]*)</A>'
        matches = re.findall(pattern, content, re.IGNORECASE)
        count = 0
        for url, title in matches:
            title = html_mod.unescape(title.strip())
            url = html_mod.unescape(url.strip())
            if url and storage.add_bookmark(title or url, url):
                count += 1
        self._populate_bookmarks_menu()
        self._update_bookmark_btn(self._current_view().url())
        self._status.showMessage(f"Imported {count} new bookmarks", 3000)

    # ------------------------------------------------------------------
    # Filter list auto-update
    # ------------------------------------------------------------------

    def _check_filterlist_freshness(self):
        if not self._settings.get("enable_adblock", True):
            return
        last_update = self._settings.get("filterlist_last_update", 0)
        if time.time() - last_update > 24 * 3600:
            self._auto_update_filterlists()

    def _auto_update_filterlists(self):
        if not self._settings.get("enable_adblock", True):
            return
        try:
            filterlists.download_all_enabled()
            self._adblocker.reload_hosts()
            self._cosmetic_css = filterlists.get_cosmetic_css()
            self._settings["filterlist_last_update"] = time.time()
            storage.save_settings(self._settings)
            self._update_adblock_label()
            self._status.showMessage("Filter lists updated", 3000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Cookie manager
    # ------------------------------------------------------------------

    def _on_cookie_removed(self, cookie):
        from PyQt6.QtNetwork import QNetworkCookie
        target = QNetworkCookie(cookie)
        self._all_cookies[:] = [
            c for c in self._all_cookies
            if not (c.domain() == target.domain() and c.name() == target.name()
                    and c.path() == target.path())
        ]

    def _show_cookie_manager(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Cookie Manager")
        dialog.setMinimumSize(620, 500)
        dialog.setStyleSheet(style.SETTINGS_FORM_STYLE)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        search = QLineEdit()
        search.setPlaceholderText("  Filter by domain...")
        search.setStyleSheet(style.SEARCH_INPUT_STYLE)
        layout.addWidget(search)

        count_label = QLabel("")
        count_label.setStyleSheet(f"color: {style.TEXT_DIM}; font-size: 12px;")
        layout.addWidget(count_label)

        listw = QListWidget()
        listw.setStyleSheet(style.LIST_WIDGET_STYLE)
        layout.addWidget(listw)

        cookie_store = self._profile.cookieStore()
        cookies = self._all_cookies

        def populate(filter_text=""):
            listw.clear()
            ft = filter_text.lower()
            domains = {}
            for c in cookies:
                domain = c.domain()
                if ft and ft not in domain.lower():
                    continue
                if domain not in domains:
                    domains[domain] = []
                domains[domain].append(c)
            count_label.setText(
                f"{len(cookies)} cookies from {len(domains)} domains"
                if not ft else f"Showing {sum(len(v) for v in domains.values())} cookies")
            for domain in sorted(domains.keys()):
                for c in domains[domain]:
                    name = c.name().data().decode('utf-8', errors='replace')
                    item = QListWidgetItem(f"{domain}  \u2014  {name}")
                    item.setData(Qt.ItemDataRole.UserRole, c)
                    listw.addItem(item)

        populate()
        search.textChanged.connect(populate)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        delete_all_btn = QPushButton("Delete All")
        delete_all_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        from PyQt6.QtCore import QTimer

        def _repopulate():
            QTimer.singleShot(100, lambda: populate(search.text()))

        def delete_selected():
            item = listw.currentItem()
            if item:
                cookie = item.data(Qt.ItemDataRole.UserRole)
                cookie_store.deleteCookie(cookie)
                _repopulate()

        def delete_all():
            reply = QMessageBox.question(
                dialog, "Delete All Cookies",
                "Delete all cookies? You will be logged out of all sites.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                cookie_store.deleteAllCookies()
                _repopulate()

        delete_btn.clicked.connect(delete_selected)
        delete_all_btn.clicked.connect(delete_all)
        close_btn.clicked.connect(dialog.close)

        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(delete_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    # ------------------------------------------------------------------
    # Site permissions
    # ------------------------------------------------------------------

    def _show_permission_prompt(self, origin, feature, feature_name, host):
        descriptions = {
            "geolocation": "access your location",
            "microphone": "use your microphone",
            "camera": "use your camera",
            "camera_microphone": "use your camera and microphone",
            "notifications": "show notifications",
            "screen_share": "share your screen",
            "screen_share_audio": "share your screen with audio",
        }
        desc = descriptions.get(feature_name, f"use {feature_name}")

        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background: {style.BG_CARD};
                border-bottom: 1px solid {style.BORDER};
                padding: 8px 14px;
            }}
            QLabel {{ color: {style.TEXT}; font-size: 13px; }}
        """)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 6, 12, 6)

        label = QLabel(f"\U0001f6e1  {host} wants to {desc}")
        allow_btn = QPushButton("Allow")
        allow_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        deny_btn = QPushButton("Deny")
        deny_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        remember_check = QCheckBox("Remember")
        remember_check.setChecked(True)
        remember_check.setStyleSheet(f"color: {style.TEXT_DIM}; font-size: 12px;")

        bar_layout.addWidget(label)
        bar_layout.addStretch()
        bar_layout.addWidget(remember_check)
        bar_layout.addWidget(deny_btn)
        bar_layout.addWidget(allow_btn)

        view = self._current_view()

        def respond(allowed):
            policy = (QWebEnginePage.PermissionPolicy.PermissionGrantedByUser if allowed
                      else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
            if view:
                view.page().setFeaturePermission(origin, feature, policy)
            if remember_check.isChecked():
                storage.set_permission(host, feature_name, "allow" if allowed else "deny")
            bar.setParent(None)
            bar.deleteLater()

        allow_btn.clicked.connect(lambda: respond(True))
        deny_btn.clicked.connect(lambda: respond(False))

        self._central_layout.insertWidget(0, bar)

    def _show_permissions(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Site Permissions")
        dialog.setMinimumSize(560, 440)
        dialog.setStyleSheet(style.SETTINGS_FORM_STYLE)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        listw = QListWidget()
        listw.setStyleSheet(style.LIST_WIDGET_STYLE)

        perms = storage.load_permissions()
        for host, features in sorted(perms.items()):
            for feat, decision in sorted(features.items()):
                icon = "\u2705" if decision == "allow" else "\u274c"
                item = QListWidgetItem(f"{icon}  {host}  \u2014  {feat}  ({decision})")
                item.setData(Qt.ItemDataRole.UserRole, (host, feat))
                listw.addItem(item)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        delete_btn = QPushButton("Remove Selected")
        delete_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        clear_btn = QPushButton("Remove All")
        clear_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        def delete_selected():
            item = listw.currentItem()
            if item:
                h, f = item.data(Qt.ItemDataRole.UserRole)
                storage.remove_permission(h, f)
                listw.takeItem(listw.row(item))

        def clear_all():
            reply = QMessageBox.question(dialog, "Remove All Permissions",
                "Remove all saved site permissions?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                storage.save_permissions({})
                listw.clear()

        delete_btn.clicked.connect(delete_selected)
        clear_btn.clicked.connect(clear_all)
        close_btn.clicked.connect(dialog.close)

        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addWidget(listw)
        layout.addLayout(btn_layout)
        dialog.exec()

    # ------------------------------------------------------------------
    # Session save / restore
    # ------------------------------------------------------------------

    def _restore_session_or_new_tab(self):
        """On startup, restore previous session with lazy loading, or open a new tab."""
        if self._settings.get("restore_session", True) and not self._private_mode:
            session = storage.load_session()
            if session:
                pinned_indices = []
                for i, tab_info in enumerate(session):
                    url = tab_info.get("url", "")
                    title = tab_info.get("title", "")
                    if url and not url.startswith("shroud:"):
                        if i == 0:
                            self.add_new_tab(url)
                        else:
                            self._add_lazy_tab(url, title)
                        if tab_info.get("pinned", False):
                            pinned_indices.append(self._tabs.count() - 1)
                # Restore pinned state
                for idx in pinned_indices:
                    self._pin_tab(idx)
                if self._tabs.count() > 0:
                    return
        self.add_new_tab()

    def _add_lazy_tab(self, url, title=""):
        """Create a tab that doesn't load until selected."""
        view = ShroudWebView(self._profile, tab_widget=self)
        view.setZoomFactor(self._settings.get("default_zoom", 100) / 100.0)
        view.page().https_only = self._settings.get("https_only", False)
        view._deferred_url = url

        display = title[:30] + "\u2026" if len(title) > 30 else (title or url[:30])
        i = self._tabs.addTab(view, display or "Loading\u2026")
        self._tabs.setTabToolTip(i, title or url)

        view.urlChanged.connect(partial(self._tab_url_changed, view))
        view.titleChanged.connect(partial(self._tab_title_changed, view))
        view.iconChanged.connect(partial(self._tab_icon_changed, view))
        view.loadStarted.connect(self._load_started)
        view.loadProgress.connect(self._load_progress)
        view.loadFinished.connect(self._load_finished)
        view.page().fullScreenRequested.connect(self._handle_fullscreen_request)
        view.page().recentlyAudibleChanged.connect(partial(self._tab_audio_changed, view))

        # Show placeholder
        view.setHtml(
            f'<html><body style="background:#111115;color:#5c5c6b;display:flex;'
            f'align-items:center;justify-content:center;height:100vh;margin:0;'
            f'font-family:sans-serif;font-size:14px;">'
            f'<div style="text-align:center">'
            f'<div style="font-size:16px;margin-bottom:8px;">{title or url}</div>'
            f'<div>Switch to this tab to load</div></div></body></html>',
            QUrl("shroud://lazy"),
        )
        return view

    def closeEvent(self, event):
        """Save session on close."""
        if self._settings.get("restore_session", True) and not self._private_mode:
            tabs = []
            for i in range(self._tabs.count()):
                view = self._tabs.widget(i)
                if view:
                    # Check for deferred (lazy) URL first
                    deferred = getattr(view, "_deferred_url", None)
                    url = deferred or view.url().toString()
                    title = view.title() or self._tabs.tabText(i)
                    if url and not url.startswith("shroud:"):
                        tabs.append({
                            "url": url, "title": title,
                            "pinned": getattr(view, '_pinned', False),
                        })
            if tabs:
                storage.save_session(tabs)
            else:
                storage.clear_session()
        # Lock the password vault
        self._vault.lock()

        # Close detached (popup) windows first
        for win in list(getattr(self, "_detached_windows", [])):
            win.close()
        self._detached_windows = []

        # Delete pages before the profile, but AFTER Qt has flushed cookies
        # to disk.  Setting the page to None before the profile is destroyed
        # prevents the "profile requested but page still not deleted" warning
        # while letting the cookie store persist session data.
        for i in range(self._tabs.count()):
            view = self._tabs.widget(i)
            if view and view.page():
                view.page().deleteLater()

        event.accept()

    # ------------------------------------------------------------------
    # Clear browsing data
    # ------------------------------------------------------------------

    def _show_clear_data(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Clear Browsing Data")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(style.SETTINGS_FORM_STYLE)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        info = QLabel("Select data to clear:")
        layout.addWidget(info)

        history_check = QCheckBox("Browsing History")
        history_check.setChecked(True)
        cookies_check = QCheckBox("Cookies")
        cache_check = QCheckBox("Cache")
        passwords_check = QCheckBox("Saved Passwords")

        layout.addWidget(history_check)
        layout.addWidget(cookies_check)
        layout.addWidget(cache_check)
        layout.addWidget(passwords_check)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        clear_btn = QPushButton("Clear Data")
        clear_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        clear_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            cleared = []
            if history_check.isChecked():
                storage.clear_history()
                self._refresh_suggestions()
                cleared.append("history")
            if cookies_check.isChecked():
                self._profile.cookieStore().deleteAllCookies()
                cleared.append("cookies")
            if cache_check.isChecked():
                self._profile.clearHttpCache()
                cleared.append("cache")
            if passwords_check.isChecked():
                if self._vault.is_setup() or self._vault.is_keyring_setup():
                    from .storage import DATA_DIR
                    from . import keyring_backend
                    for fname in ("passwords.enc", "passwords.salt", "passwords.verify"):
                        p = DATA_DIR / fname
                        if p.exists():
                            p.unlink()
                    keyring_backend.delete_secret("vault_fernet_key")
                    self._settings["vault_backend"] = "master_password"
                    storage.save_settings(self._settings)
                    self._vault.lock()
                    cleared.append("passwords")

            if cleared:
                self._status.showMessage(f"Cleared: {', '.join(cleared)}", 4000)

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
