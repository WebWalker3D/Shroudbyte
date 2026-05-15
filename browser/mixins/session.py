import sys
from functools import partial

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QApplication

from browser import storage
from browser.webview import ShroudWebView


class SessionMixin:
    """Session save / restore methods extracted from MainWindow."""

    def _signal_handler(self, signum, frame):
        """Save session and exit on SIGTERM/SIGINT."""
        self._autosave_session()
        self._vault.lock()
        QApplication.quit()

    def _mark_session_dirty(self):
        """Mark that session state has changed and needs saving."""
        self._session_dirty = True

    def _autosave_session(self):
        """Periodically save the current session to disk."""
        if not self._settings.get("restore_session", True) or self._private_mode:
            return
        if not getattr(self, '_session_dirty', True):
            return
        self._session_dirty = False
        tabs = []
        for i in range(self._tabs.count()):
            view = self._tabs.widget(i)
            if view:
                deferred = getattr(view, "_deferred_url", None)
                url = deferred or view.url().toString()
                title = view.title() or self._tabs.tabText(i)
                if url and not url.startswith("shroud:"):
                    tab_data = {
                        "url": url, "title": title,
                        "pinned": getattr(view, '_pinned', False),
                    }
                    note = getattr(view, '_tab_note', '')
                    if note:
                        tab_data["note"] = note
                    tabs.append(tab_data)
        if tabs:
            storage.save_session(tabs)

    def _restore_session_or_new_tab(self):
        """On startup, restore previous session with lazy loading, or open a new tab."""
        if self._settings.get("restore_session", True) and not self._private_mode:
            session = storage.load_session()
            if session:
                pinned_indices = []
                for i, tab_info in enumerate(session):
                    url = tab_info.get("url", "")
                    title = tab_info.get("title", "")
                    note = tab_info.get("note", "")
                    if url and not url.startswith("shroud:"):
                        if i == 0:
                            self.add_new_tab(url)
                        else:
                            self._add_lazy_tab(url, title)
                        if note:
                            view = self._tabs.widget(self._tabs.count() - 1)
                            if view:
                                view._tab_note = note
                                self._update_tab_tooltip(self._tabs.count() - 1)
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
        view.loadStarted.connect(partial(self._load_started, view))
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
        # Persist window state (size + maximized/fullscreen) so the next
        # launch restores how the user left it.
        if not self._private_mode:
            if self.isFullScreen():
                mode = "fullscreen"
            elif self.isMaximized():
                mode = "maximized"
            else:
                mode = "normal"
            geo = self.normalGeometry() if mode != "normal" else self.geometry()
            storage.save_window_state({
                "state": mode,
                "x": geo.x(),
                "y": geo.y(),
                "width": geo.width(),
                "height": geo.height(),
            })
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
        # Stop page watcher and screen time tracker
        self._page_watcher.stop()
        self._screen_time.stop()
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
