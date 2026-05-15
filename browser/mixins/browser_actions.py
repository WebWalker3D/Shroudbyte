from PyQt6.QtCore import Qt, QUrl, QSize
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QFrame, QCheckBox, QMessageBox, QWidget,
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PyQt6.QtWebEngineCore import QWebEnginePage

from browser import storage, style
from browser.passworddialogs import HttpAuthDialog
from browser.webview import ShroudWebView

import os
import json
import time


class BrowserActionsMixin:

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _show_history(self):
        view = self._current_view()
        if view:
            view.load(QUrl("shroud://history"))
        else:
            self.add_new_tab(QUrl("shroud://history"))

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
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Print Preview")
        preview.resize(900, 800)

        def _render(prn):
            # Synchronous wrapper around the async view.print() call so the
            # preview can rasterize before showing.
            loop_done = {"v": False}
            def _cb(_ok):
                loop_done["v"] = True
            view.page().print(prn, _cb)
            from PyQt6.QtCore import QEventLoop, QTimer
            loop = QEventLoop()
            timer = QTimer()
            timer.setInterval(50)
            timer.timeout.connect(lambda: loop_done["v"] and loop.quit())
            timer.start()
            # Hard cap so a stuck render can't hang the dialog.
            QTimer.singleShot(15000, loop.quit)
            loop.exec()

        preview.paintRequested.connect(_render)
        if preview.exec() == QDialog.DialogCode.Accepted:
            self._status.showMessage("Page printed", 3000)

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
        import threading
        import urllib.request
        from PyQt6.QtCore import QTimer

        url_string = url.toString()
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()

        def _worker():
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
                decoded = html.decode(charset, errors="replace")
                QTimer.singleShot(0, lambda: self._apply_authed_page(decoded, url))
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    QTimer.singleShot(0, lambda: self._on_auth_failed(host, url))
                else:
                    QTimer.singleShot(0, lambda: self._status.showMessage(
                        f"HTTP error {e.code} loading {host}", 5000))
            except Exception as e:
                msg = str(e)
                QTimer.singleShot(0, lambda: self._status.showMessage(
                    f"Failed to load {host}: {msg}", 5000))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_authed_page(self, html, url):
        view = self._current_view()
        if view:
            view.page().setHtml(html, url)

    def _on_auth_failed(self, host, url):
        self._adblocker.clear_http_auth(host)
        self._prompt_http_auth(url)

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
            self._pending_source_url = view.url().toString()
            view.page().toHtml(self._open_source_tab)

    def _open_source_tab(self, html):
        self._pending_source_html = html
        self.add_new_tab(QUrl("shroud://source"))

    # ------------------------------------------------------------------
    # Quick save page offline
    # ------------------------------------------------------------------

    def _quick_save_page(self):
        """Save the current page as an offline snapshot with one keystroke."""
        view = self._current_view()
        if not view:
            return
        url = view.url().toString()
        if not url or url.startswith("shroud:"):
            self._status.showMessage("Cannot save internal pages", 2000)
            return
        title = view.title() or url
        view.page().toHtml(lambda html: self._finish_save_page(url, title, html))

    def _finish_save_page(self, url, title, html):
        from .pagewatcher import _extract_text
        preview = _extract_text(html)[:200] if html else ""
        storage.save_page(url, title, html, preview)
        self._status.showMessage(f"Saved: {title[:50]}", 3000)

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
        from browser.mainwindow import MainWindow
        win = MainWindow()
        win.show()

    def _open_private_window(self):
        from browser.mainwindow import MainWindow
        from browser import __app_name__
        win = MainWindow(private_mode=True)
        win.setWindowTitle(f"Private — {__app_name__}")
        win.show()

    def _reopen_closed_tab(self):
        if not self._closed_tabs:
            self._status.showMessage("No recently closed tabs", 2000)
            return
        tab_info = self._closed_tabs.pop()
        self.add_new_tab(tab_info["url"])

    # ------------------------------------------------------------------
    # Command Palette
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def _export_browser_data(self):
        """Export encrypted browser state to a file."""
        import threading
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        from browser.export import export_state, EXPORT_COLLECTIONS
        from browser import style

        # Password dialog
        password, ok = QInputDialog.getText(
            self, "Export Password",
            "Enter a password to encrypt the export:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return

        # File dialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Browser Data",
            os.path.expanduser(f"~/shroudbyte_export_{int(time.time())}.sbe"),
            "Shroudbyte Export (*.sbe)",
        )
        if not path:
            return

        self._status.showMessage("Exporting…")

        def _worker():
            try:
                data = export_state(password)
                with open(path, "wb") as f:
                    f.write(data)
                basename = os.path.basename(path)
                QTimer.singleShot(0, lambda: self._status.showMessage(
                    f"Exported to {basename}", 3000))
            except Exception as e:
                msg = str(e)
                QTimer.singleShot(0, lambda: QMessageBox.critical(
                    self, "Export Failed", msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _import_browser_data(self):
        """Import encrypted browser state from a file."""
        import threading
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        from browser.export import import_state

        path, _ = QFileDialog.getOpenFileName(
            self, "Import Browser Data",
            os.path.expanduser("~"),
            "Shroudbyte Export (*.sbe);;All Files (*)",
        )
        if not path:
            return

        password, ok = QInputDialog.getText(
            self, "Import Password",
            "Enter the export password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return

        self._status.showMessage("Importing…")

        def _worker():
            try:
                with open(path, "rb") as f:
                    data = f.read()
                result = import_state(data, password)
                summary = ", ".join(f"{name}: {count}" for name, count in result.items())
                QTimer.singleShot(0, lambda: self._status.showMessage(
                    f"Imported: {summary}", 5000))
            except Exception as e:
                msg = str(e)
                QTimer.singleShot(0, lambda: QMessageBox.critical(
                    self, "Import Failed", msg))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Command Palette
    # ------------------------------------------------------------------

    def _show_command_palette(self):
        """Show a floating command palette for fuzzy-matching actions."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
        )
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QAction

        from browser import style

        dialog = QDialog(self)
        dialog.setWindowTitle("Command Palette")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet(style.SETTINGS_FORM_STYLE)

        layout = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setPlaceholderText("Type a command...")
        search.setStyleSheet(style.URL_BAR_STYLE)
        layout.addWidget(search)

        results = QListWidget()
        results.setStyleSheet(
            f"QListWidget {{ background: {style.BG_CARD}; color: {style.TEXT}; "
            f"border: none; }} "
            f"QListWidget::item {{ padding: 8px; }} "
            f"QListWidget::item:selected {{ background: {style.ACCENT}; }}"
        )
        layout.addWidget(results)

        # Build command list from menu actions + common operations
        commands = []
        for action in self.findChildren(QAction):
            text = action.text().replace("&", "")
            shortcut = action.shortcut().toString() if action.shortcut() else ""
            if text and action.isEnabled():
                commands.append((text, shortcut, action))

        def filter_commands(text):
            results.clear()
            query = text.lower()
            for name, shortcut, action in commands:
                if not query or query in name.lower():
                    display = f"{name}  ({shortcut})" if shortcut else name
                    item = QListWidgetItem(display)
                    item.setData(Qt.ItemDataRole.UserRole, action)
                    results.addItem(item)
            if results.count() > 0:
                results.setCurrentRow(0)

        def activate(item):
            if not item:
                return
            action = item.data(Qt.ItemDataRole.UserRole)
            dialog.accept()
            if action:
                action.trigger()

        search.textChanged.connect(filter_commands)
        results.itemActivated.connect(activate)

        # Enter key on search activates first result
        search.returnPressed.connect(
            lambda: activate(results.currentItem()) if results.currentItem() else None
        )

        filter_commands("")
        dialog.exec()
