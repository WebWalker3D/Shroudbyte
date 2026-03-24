from functools import partial

from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtWidgets import (
    QMenu, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QInputDialog, QMessageBox,
    QApplication, QFrame, QMainWindow, QTabBar,
)
from PyQt6.QtGui import QIcon, QKeySequence, QAction

from browser import storage, style
from browser.webview import ShroudWebView
from browser.screentime import ScreenTimeTracker
from browser.pwa import detect_manifest_js


class TabMixin:

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

        note = getattr(view, '_tab_note', '') if view else ''
        if note:
            menu.addAction("Edit Note\u2026", lambda: self._edit_tab_note(index))
            menu.addAction("Remove Note", lambda: self._remove_tab_note(index))
        else:
            menu.addAction("Add Note\u2026", lambda: self._edit_tab_note(index))
        menu.addSeparator()

        # Container profile submenu
        if hasattr(self, '_profile_manager'):
            container_menu = QMenu("Move to Container", menu)
            current_profile = getattr(view, '_container_profile', 'Default') if view else 'Default'
            for p in self._profile_manager.list_profiles():
                action_text = f"\u25cf {p.name}" if p.name == current_profile else p.name
                container_menu.addAction(
                    action_text,
                    partial(self._move_tab_to_container, index, p.name),
                )
            menu.addMenu(container_menu)
            menu.addSeparator()

        menu.addAction("Close Tab", lambda: self._close_tab(index))
        menu.addAction("Close Other Tabs", lambda: self._close_other_tabs(index))
        menu.addSeparator()
        menu.addAction("Group Tabs by Site", self._group_tabs_by_domain)
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

    def _group_tabs_by_domain(self):
        """Sort tabs by domain, keeping pinned tabs in place."""
        current_view = self._current_view()
        bar = self._tabs.tabBar()

        # Collect unpinned tabs with their domain
        tabs = []
        pinned_count = 0
        for i in range(self._tabs.count()):
            view = self._tabs.widget(i)
            if not view:
                continue
            if getattr(view, '_pinned', False):
                pinned_count += 1
                continue
            url = getattr(view, '_deferred_url', None) or view.url().toString()
            host = QUrl(url).host().lower().removeprefix("www.") if url else ""
            tabs.append((i, view, host))

        if len(tabs) < 2:
            return

        # Sort by domain, then by original position within same domain
        tabs.sort(key=lambda t: (t[2], t[0]))

        # Reorder by moving tabs to their sorted positions
        # Work from left to right after pinned tabs
        for new_pos_offset, (old_idx, view, host) in enumerate(tabs):
            target = pinned_count + new_pos_offset
            current = self._tabs.indexOf(view)
            if current != target:
                bar.moveTab(current, target)

        # Restore focus to the originally active tab
        if current_view:
            idx = self._tabs.indexOf(current_view)
            if idx >= 0:
                self._tabs.setCurrentIndex(idx)

        # Count groups for status message
        domains = []
        for _, _, host in tabs:
            if not domains or domains[-1] != host:
                domains.append(host)
        self._status.showMessage(
            f"Grouped {len(tabs)} tabs into {len(domains)} sites", 3000
        )

    # ------------------------------------------------------------------
    # Container profiles
    # ------------------------------------------------------------------

    def _move_tab_to_container(self, index, profile_name):
        """Reopen a tab in a different container profile."""
        view = self._tabs.widget(index)
        if not view:
            return
        current = getattr(view, '_container_profile', 'Default')
        if current == profile_name:
            return
        url = view.url()
        if url.isEmpty() or url.scheme() == "shroud":
            url = QUrl(getattr(view, '_deferred_url', '') or "shroud://newtab")
        self._close_tab(index)
        self.add_new_tab(url, profile_name=profile_name)

    # ------------------------------------------------------------------
    # Tab search
    # ------------------------------------------------------------------

    def _show_tab_search(self):
        """Show a popup to search and switch between open tabs."""
        popup = QDialog(self)
        popup.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        popup.setStyleSheet(f"""
            QDialog {{
                background: {style.BG_MID};
                border: 1px solid {style.BORDER};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search open tabs\u2026")
        search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 10px 14px; font-size: 14px;
                background: {style.BG_DARK}; color: {style.TEXT};
                border: 1px solid {style.BORDER}; border-radius: 8px;
            }}
            QLineEdit:focus {{ border-color: {style.ACCENT}; }}
        """)
        layout.addWidget(search_input)

        results = QListWidget()
        results.setStyleSheet(style.LIST_WIDGET_STYLE)
        results.setMaximumHeight(400)
        layout.addWidget(results)

        # Collect all tabs
        all_tabs = []
        for i in range(self._tabs.count()):
            view = self._tabs.widget(i)
            if not view:
                continue
            title = view.title() or self._tabs.tabText(i)
            url = (getattr(view, '_deferred_url', None)
                   or view.url().toString())
            note = getattr(view, '_tab_note', '')
            all_tabs.append((i, title, url, note))

        def populate(query=""):
            results.clear()
            q = query.lower()
            for idx, title, url, note in all_tabs:
                if q and (q not in title.lower()
                          and q not in url.lower()
                          and q not in note.lower()):
                    continue
                display = title[:60]
                if note:
                    display += f"  \U0001f4cc {note[:30]}"
                item = QListWidgetItem(f"{display}\n{url[:80]}")
                item.setData(Qt.ItemDataRole.UserRole, idx)
                results.addItem(item)
            if results.count() > 0:
                results.setCurrentRow(0)

        def activate(item=None):
            item = item or results.currentItem()
            if item:
                idx = item.data(Qt.ItemDataRole.UserRole)
                self._tabs.setCurrentIndex(idx)
                popup.close()

        populate()
        search_input.textChanged.connect(populate)
        results.itemActivated.connect(activate)

        # Enter key activates, up/down navigate the list
        def on_key(event):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                activate()
            elif event.key() == Qt.Key.Key_Down:
                row = results.currentRow()
                if row < results.count() - 1:
                    results.setCurrentRow(row + 1)
            elif event.key() == Qt.Key.Key_Up:
                row = results.currentRow()
                if row > 0:
                    results.setCurrentRow(row - 1)
            elif event.key() == Qt.Key.Key_Escape:
                popup.close()
            else:
                QLineEdit.keyPressEvent(search_input, event)

        search_input.keyPressEvent = on_key

        # Position centered near top of window
        popup.resize(480, min(500, self.height() - 100))
        geo = self.geometry()
        popup.move(
            geo.x() + (geo.width() - 480) // 2,
            geo.y() + 80,
        )
        popup.show()
        search_input.setFocus()

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def add_new_tab(self, url=None, profile_name=None):
        if hasattr(self, '_mark_session_dirty'):
            self._mark_session_dirty()

        # Determine container profile
        if profile_name is None and url is not None and hasattr(self, '_profile_manager'):
            url_str = url.toString() if hasattr(url, 'toString') else str(url)
            profile_name = self._profile_manager.match_profile_for_url(url_str)

        # Select the QWebEngineProfile for this container
        if profile_name and profile_name != "Default" and hasattr(self, '_profile_manager'):
            qt_profile = self._profile_manager.get_qt_profile(profile_name)
            # Install scheme handler and ad blocker on container profiles
            if not qt_profile.urlSchemeHandler(b"shroud"):
                qt_profile.installUrlSchemeHandler(
                    b"shroud", self._scheme_handler)
            if hasattr(self, '_adblocker') and qt_profile.urlRequestInterceptor() is None:
                qt_profile.setUrlRequestInterceptor(self._adblocker)
        else:
            qt_profile = self._profile
            if not profile_name:
                profile_name = "Default"

        view = ShroudWebView(qt_profile, tab_widget=self)
        view._container_profile = profile_name
        view.setZoomFactor(self._settings.get("default_zoom", 100) / 100.0)
        view.page().https_only = self._settings.get("https_only", False)

        i = self._tabs.addTab(view, "New Tab")
        self._tabs.setCurrentIndex(i)

        # Colored tab indicator for non-default profiles
        if profile_name and profile_name != "Default" and hasattr(self, '_profile_manager'):
            profile = self._profile_manager.get_profile(profile_name)
            if profile:
                self._tabs.tabBar().setTabData(i, profile.color)

        view.urlChanged.connect(partial(self._tab_url_changed, view))
        view.titleChanged.connect(partial(self._tab_title_changed, view))
        view.iconChanged.connect(partial(self._tab_icon_changed, view))
        view.loadStarted.connect(partial(self._load_started, view))
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

    @staticmethod
    def _get_tab_domain(view):
        """Get the effective domain for a tab's current URL."""
        url = view.url()
        if url.scheme() in ("shroud", "about", "data", ""):
            return None
        host = url.host()
        if not host or host in ("localhost", "127.0.0.1", "::1"):
            return None
        return host.lower()

    def _close_tab(self, index):
        if hasattr(self, '_mark_session_dirty'):
            self._mark_session_dirty()
        widget = self._tabs.widget(index)
        if widget and getattr(widget, '_pinned', False):
            return

        # Save to closed tabs stack for Ctrl+Shift+T
        url = widget.url().toString()
        title = widget.title()
        if url and not url.startswith("shroud:"):
            self._closed_tabs.append({"url": url, "title": title})
            if len(self._closed_tabs) > 20:
                self._closed_tabs = self._closed_tabs[-20:]

        # Auto-delete cookies if this is the last tab for its domain
        if (self._settings.get("auto_delete_cookies")
                and not self._private_mode):
            closing_domain = self._get_tab_domain(widget)
            if closing_domain and not storage.is_cookie_whitelisted(closing_domain):
                is_last = True
                for i in range(self._tabs.count()):
                    if i == index:
                        continue
                    other = self._tabs.widget(i)
                    if other and self._get_tab_domain(other) == closing_domain:
                        is_last = False
                        break
                if is_last:
                    self._delete_cookies_for_domain(closing_domain)

        if self._tabs.count() <= 1:
            self.close()
            return

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
            if view.url().scheme() not in ("shroud", ""):
                self._screen_time.set_domain(view.url().host())

    def _tab_url_changed(self, view, url):
        if hasattr(self, '_mark_session_dirty'):
            self._mark_session_dirty()
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

        # Auto-delete cookies when navigating away from a domain
        if (self._settings.get("auto_delete_cookies")
                and not self._private_mode):
            new_domain = self._get_tab_domain(view)
            old_domain = getattr(view, "_last_domain", None)
            view._last_domain = new_domain
            if (old_domain and old_domain != new_domain
                    and not storage.is_cookie_whitelisted(old_domain)):
                # Check if any other tab still has this domain
                still_open = False
                for i in range(self._tabs.count()):
                    other = self._tabs.widget(i)
                    if other is not view and other and self._get_tab_domain(other) == old_domain:
                        still_open = True
                        break
                if not still_open:
                    self._delete_cookies_for_domain(old_domain)

        if view == self._current_view():
            self._update_url_bar(url)
            self._update_bookmark_btn(url)
            if url.scheme() not in ("shroud", ""):
                self._screen_time.set_domain(url.host())
            # Duplicate tab detection
            self._check_duplicate_tab(view, url)

    def _check_duplicate_tab(self, view, url):
        """Show a bar if another tab has the same URL."""
        # Dismiss previous duplicate bar if any
        if hasattr(self, '_dup_bar') and self._dup_bar:
            self._dup_bar._remove()
            self._dup_bar = None

        url_str = url.toString()
        if not url_str or url_str.startswith("shroud:"):
            return

        for i in range(self._tabs.count()):
            other = self._tabs.widget(i)
            if other is view or not other:
                continue
            other_url = (getattr(other, '_deferred_url', None)
                         or other.url().toString())
            if other_url == url_str:
                bar = QFrame()
                bar.setStyleSheet(
                    f"QFrame {{ background: {style.BG_CARD}; "
                    f"border-bottom: 1px solid {style.BORDER}; "
                    f"padding: 6px 14px; }}"
                )
                h = QHBoxLayout(bar)
                h.setContentsMargins(12, 6, 12, 6)
                h.setSpacing(10)
                label = QLabel("This page is already open in another tab.")
                label.setStyleSheet(f"color: {style.TEXT_DIM}; font-size: 13px;")
                switch_btn = QPushButton("Switch to it")
                switch_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
                switch_btn.setFixedHeight(28)
                dismiss_btn = QPushButton("Dismiss")
                dismiss_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
                dismiss_btn.setFixedHeight(28)
                other_idx = i
                bar._remove = lambda: (
                    bar.setParent(None), bar.deleteLater(),
                    setattr(self, '_dup_bar', None),
                )
                switch_btn.clicked.connect(lambda _, idx=other_idx: (
                    self._tabs.setCurrentIndex(idx), bar._remove(),
                ))
                dismiss_btn.clicked.connect(bar._remove)
                h.addWidget(label)
                h.addStretch()
                h.addWidget(switch_btn)
                h.addWidget(dismiss_btn)
                self._central_layout.insertWidget(0, bar)
                self._dup_bar = bar
                return

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
                note = getattr(view, '_tab_note', '')
                tip = f"{title}\n\U0001f4cc {note}" if note else title
                self._tabs.setTabToolTip(index, tip)
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

    # ------------------------------------------------------------------
    # Tab notes
    # ------------------------------------------------------------------

    def _edit_tab_note(self, index):
        view = self._tabs.widget(index)
        if not view:
            return
        current = getattr(view, '_tab_note', '')
        text, ok = QInputDialog.getText(
            self, "Tab Note",
            "Note for this tab:",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if ok:
            view._tab_note = text.strip()
            self._update_tab_tooltip(index)

    def _remove_tab_note(self, index):
        view = self._tabs.widget(index)
        if view:
            view._tab_note = ''
            self._update_tab_tooltip(index)

    def _update_tab_tooltip(self, index):
        view = self._tabs.widget(index)
        if not view:
            return
        title = view.title() or view.url().toString()
        note = getattr(view, '_tab_note', '')
        if note:
            self._tabs.setTabToolTip(index, f"{title}\n\U0001f4cc {note}")
        else:
            self._tabs.setTabToolTip(index, title)

    def _tab_icon_changed(self, view, icon):
        index = self._tabs.indexOf(view)
        if index >= 0:
            self._tabs.setTabIcon(index, icon)

    def _switch_to_tab(self, index):
        if index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    def _current_view(self):
        return self._tabs.currentWidget()
