import html as html_mod
import re
import time

from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)
from PyQt6.QtWebEngineCore import QWebEnginePage

from browser import filterlists, permission_ledger, storage, style


class DataManagementMixin:
    """Filter lists, cookies, permissions, clear-data, bookmarks I/O,
    screenshots, PiP, and about — mixed into BrowserWindow."""

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
        # Netscape bookmark format uses <DL>/<DT><H3>Folder</H3><DL>...</DL>
        # nesting. Walk the file linearly: H3 pushes a folder, </DL> pops.
        token_pattern = re.compile(
            r'<H3[^>]*>([^<]*)</H3>'              # group 1: folder name
            r'|<A\s+HREF="([^"]+)"[^>]*>([^<]*)</A>'  # 2,3: url, title
            r'|</DL>',
            re.IGNORECASE,
        )
        folder_stack: list[str] = []
        count = 0
        for m in token_pattern.finditer(content):
            folder_name, url, title = m.group(1), m.group(2), m.group(3)
            if folder_name is not None:
                folder_stack.append(html_mod.unescape(folder_name.strip()))
            elif url is not None:
                title = html_mod.unescape((title or "").strip())
                url = html_mod.unescape(url.strip())
                folder_path = "/".join(folder_stack)
                if url and storage.add_bookmark(title or url, url, folder=folder_path):
                    count += 1
            else:
                # </DL> — pop the most recent folder if any.
                if folder_stack:
                    folder_stack.pop()
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
        import threading

        def _worker():
            try:
                filterlists.download_all_enabled()
                css = filterlists.get_cosmetic_css()
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._apply_filterlist_update(css))
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_filterlist_update(self, css):
        """Apply downloaded filter list results on the GUI thread."""
        self._adblocker.reload_hosts()
        self._cosmetic_css = css
        self._settings["filterlist_last_update"] = time.time()
        storage.save_settings(self._settings)
        self._update_adblock_label()
        self._status.showMessage("Filter lists updated", 3000)

    # ------------------------------------------------------------------
    # Cookie manager
    # ------------------------------------------------------------------

    def _delete_cookies_from_db(self, cookies: list[dict]) -> int:
        """Delete specific cookies directly from Chromium's SQLite database."""
        import sqlite3
        db_path = storage.DATA_DIR / "webengine" / "Cookies"
        if not db_path.exists():
            return 0
        try:
            conn = sqlite3.connect(str(db_path))
            deleted = 0
            for c in cookies:
                conn.execute(
                    "DELETE FROM cookies WHERE host_key = ? AND name = ? AND path = ?",
                    (c["domain"], c["name"], c["path"]),
                )
                deleted += conn.total_changes if deleted == 0 else 0
            conn.commit()
            deleted = conn.total_changes
            conn.close()
            # Tell Chromium to reload from disk
            self._profile.cookieStore().loadAllCookies()
            return deleted
        except Exception:
            return 0

    def _delete_all_cookies_from_db(self) -> int:
        """Delete all cookies from Chromium's SQLite database."""
        import sqlite3
        db_path = storage.DATA_DIR / "webengine" / "Cookies"
        if not db_path.exists():
            return 0
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("DELETE FROM cookies")
            conn.commit()
            deleted = conn.total_changes
            conn.close()
            self._profile.cookieStore().loadAllCookies()
            return deleted
        except Exception:
            return 0

    def _delete_cookies_for_domain(self, domain):
        """Delete all cookies whose domain matches the given host."""
        db_cookies = self._load_cookies_from_db()
        to_delete = []
        for c in db_cookies:
            cd = c["domain"].lstrip(".")
            if cd == domain or domain.endswith("." + cd) or cd.endswith("." + domain):
                to_delete.append(c)
        if to_delete:
            self._delete_cookies_from_db(to_delete)
            self._show_cookie_toast(domain, len(to_delete))

    def _show_cookie_toast(self, domain, count):
        """Show a brief notification that cookies were cleared."""
        self._status.showMessage(
            f"Auto-deleted {count} cookie{'s' if count != 1 else ''} for {domain}", 4000
        )

    def _on_cookie_added(self, cookie):
        from PyQt6.QtNetwork import QNetworkCookie
        self._all_cookies.append(QNetworkCookie(cookie))

    def _on_cookie_removed(self, cookie):
        from PyQt6.QtNetwork import QNetworkCookie
        target = QNetworkCookie(cookie)
        self._all_cookies[:] = [
            c for c in self._all_cookies
            if not (c.domain() == target.domain() and c.name() == target.name()
                    and c.path() == target.path())
        ]

    def _load_cookies_from_db(self) -> list[dict]:
        """Read cookies directly from Chromium's SQLite database."""
        import sqlite3
        db_path = storage.DATA_DIR / "webengine" / "Cookies"
        if not db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.execute(
                "SELECT host_key, name, path, value, encrypted_value, "
                "is_httponly, is_secure, is_persistent "
                "FROM cookies ORDER BY host_key, name"
            )
            rows = cursor.fetchall()
            conn.close()
            return [
                {"domain": r[0], "name": r[1], "path": r[2],
                 "httponly": bool(r[5]), "secure": bool(r[6]),
                 "persistent": bool(r[7])}
                for r in rows
            ]
        except Exception:
            return []

    def _show_cookie_manager(self):
        db_cookies = self._load_cookies_from_db()

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

        from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setStyleSheet(style.LIST_WIDGET_STYLE)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(tree)

        cookie_store = self._profile.cookieStore()
        _cookie_map = {}  # maps tree item id -> cookie dict

        def populate(filter_text=""):
            tree.clear()
            _cookie_map.clear()
            ft = filter_text.lower()
            domains = {}
            for c in db_cookies:
                domain = c["domain"]
                if ft and ft not in domain.lower():
                    continue
                if domain not in domains:
                    domains[domain] = []
                domains[domain].append(c)
            total = len(db_cookies)
            shown = sum(len(v) for v in domains.values())
            count_label.setText(
                f"{total} cookies from {len(set(c['domain'] for c in db_cookies))} domains"
                if not ft else f"Showing {shown} cookies")
            for domain in sorted(domains.keys()):
                clean = domain.lstrip(".")
                wl = storage.is_cookie_whitelisted(clean)
                label = f"{domain}  ({len(domains[domain])})"
                if wl:
                    label += "  \u2605 kept"
                parent = QTreeWidgetItem(tree, [label])
                parent.setForeground(0, QColor(style.GREEN if wl else style.ACCENT))
                parent.setExpanded(True)
                for c in domains[domain]:
                    flags = ""
                    if c["httponly"]:
                        flags += " [HttpOnly]"
                    if c["secure"]:
                        flags += " [Secure]"
                    child = QTreeWidgetItem(parent, [f"{c['name']}{flags}"])
                    _cookie_map[id(child)] = c

        populate()
        search.textChanged.connect(populate)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        delete_all_btn = QPushButton("Delete All")
        delete_all_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        whitelist_btn = QPushButton("Toggle Keep")
        whitelist_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        whitelist_btn.setToolTip("Toggle whitelist — kept domains survive auto-delete")
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        def delete_selected():
            items = tree.selectedItems()
            if not items:
                return
            to_delete = []
            for item in items:
                c = _cookie_map.get(id(item))
                if c:
                    to_delete.append(c)
                elif item.childCount() > 0:
                    for i in range(item.childCount()):
                        cc = _cookie_map.get(id(item.child(i)))
                        if cc:
                            to_delete.append(cc)
            if to_delete:
                self._delete_cookies_from_db(to_delete)
                for c in to_delete:
                    if c in db_cookies:
                        db_cookies.remove(c)
            populate(search.text())

        def delete_all():
            reply = QMessageBox.question(
                dialog, "Delete All Cookies",
                "Delete all cookies? You will be logged out of all sites.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self._delete_all_cookies_from_db()
                db_cookies.clear()
                populate(search.text())

        def toggle_whitelist():
            items = tree.selectedItems()
            for item in items:
                if item.parent() is None:
                    domain = item.text(0).split("  (")[0].strip().lstrip(".")
                else:
                    c = _cookie_map.get(id(item))
                    if c:
                        domain = c["domain"].lstrip(".")
                    else:
                        continue
                if storage.is_cookie_whitelisted(domain):
                    storage.remove_cookie_whitelist(domain)
                else:
                    storage.add_cookie_whitelist(domain)
            populate(search.text())

        delete_btn.clicked.connect(delete_selected)
        delete_all_btn.clicked.connect(delete_all)
        whitelist_btn.clicked.connect(toggle_whitelist)
        close_btn.clicked.connect(dialog.close)

        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(delete_all_btn)
        btn_layout.addWidget(whitelist_btn)
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
                ttl = self._settings.get("permission_ttl_days", 30)
                storage.set_permission(host, feature_name, "allow" if allowed else "deny", ttl_days=ttl)
            permission_ledger.log_usage(host, feature_name, "grant" if allowed else "deny")
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
            for feat, entry in sorted(features.items()):
                # Support both old format (bare string) and new format (dict)
                if isinstance(entry, dict):
                    decision = entry.get("decision", "allow")
                else:
                    decision = entry
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
    # Permission ledger actions (from shroud://permissions page)
    # ------------------------------------------------------------------

    def _handle_perm_ledger_action(self, data):
        action = data.get("action", "")
        if action == "export":
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Permission Log", "permission_log.csv",
                "CSV files (*.csv);;All files (*)")
            if path:
                permission_ledger.export_log(path)
                self._status.showMessage(f"Permission log exported to {path}", 4000)

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
