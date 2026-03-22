"""Privacy Dashboard — per-site control panel for trackers, cookies, and permissions."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import storage, style


class PrivacyPanel(QDialog):
    """Shows a per-site privacy dashboard with granular controls."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self._mw = main_window
        self._site_host = ""
        self._needs_reload = False
        self._setup_ui()
        self._populate()

    # ── UI construction ──────────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("Privacy Dashboard")
        self.setMinimumWidth(460)
        self.setMaximumWidth(540)
        self.setStyleSheet(style.PRIVACY_PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(
            f"QFrame {{ background: {style.BG_CARD}; "
            f"border-bottom: 1px solid {style.BORDER}; padding: 16px 20px; }}"
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self._title_label = QLabel("Privacy Dashboard")
        self._title_label.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {style.TEXT};"
        )
        self._site_label = QLabel()
        self._site_label.setStyleSheet(f"font-size: 12px; color: {style.TEXT_DIM};")
        header_layout.addWidget(self._title_label)
        header_layout.addWidget(self._site_label)
        outer.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 12, 16, 16)
        self._content_layout.setSpacing(12)
        scroll.setWidget(self._content)
        outer.addWidget(scroll, 1)

        # Footer
        self._footer = QFrame()
        self._footer.setStyleSheet(
            f"QFrame {{ background: {style.BG_CARD}; "
            f"border-top: 1px solid {style.BORDER}; padding: 10px 20px; }}"
        )
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        self._reload_hint = QLabel()
        self._reload_hint.setStyleSheet(
            f"font-size: 11px; color: {style.YELLOW};"
        )
        footer_layout.addWidget(self._reload_hint)
        footer_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)
        outer.addWidget(self._footer)

        screen = self.parent().screen() if self.parent() else None
        if screen:
            max_h = int(screen.availableGeometry().height() * 0.75)
            self.resize(480, min(680, max_h))

    # ── data population ──────────────────────────────────────────

    def _populate(self):
        view = self._mw._current_view()
        if not view:
            self._site_label.setText("No active tab")
            return

        url = view.url()
        self._site_host = (url.host() or "").lower()
        scheme = url.scheme()
        is_secure = scheme == "https"

        # Site identity
        sec_icon = "\U0001f512" if is_secure else "\u26A0"
        sec_text = "Secure" if is_secure else "Not secure"
        sec_color = style.GREEN if is_secure else style.RED
        self._site_label.setText(
            f'{sec_icon}  <span style="color:{sec_color}">{sec_text}</span>'
            f'  <span style="color:{style.TEXT_DIM}">({scheme})</span>'
            f'  {self._site_host}'
        )
        self._site_label.setTextFormat(Qt.TextFormat.RichText)

        self._add_tracker_section()
        self._add_cookie_section()
        self._add_permission_section()
        self._add_tracking_params_section()
        self._content_layout.addStretch()

    # ── tracker section ──────────────────────────────────────────

    def _add_tracker_section(self):
        page_data = self._mw._adblocker.get_page_data(self._site_host)
        blocked = page_data.blocked if page_data else {}
        allowed_3p = page_data.third_party if page_data else {}
        site_exc = storage.load_site_exceptions().get(self._site_host, {})

        total_blocked = sum(blocked.values())
        total_allowed = sum(allowed_3p.values())

        self._add_section_header(
            f"Trackers & Third Parties"
            f"  ({total_blocked} blocked \u00b7 {total_allowed} allowed)"
        )

        box = self._make_section_box()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)

        if not blocked and not allowed_3p:
            empty = QLabel("No third-party requests detected yet.")
            empty.setStyleSheet(f"color: {style.TEXT_FAINT}; font-size: 12px; padding: 8px 0;")
            layout.addWidget(empty)
            self._content_layout.addWidget(box)
            return

        # Blocked trackers
        for host, count in sorted(blocked.items(), key=lambda x: -x[1]):
            is_exception = site_exc.get(host) == "allow"
            row = self._make_tracker_row(
                host, count, is_blocked=True, is_exception=is_exception
            )
            layout.addWidget(row)

        # Allowed third-party
        for host, count in sorted(allowed_3p.items(), key=lambda x: -x[1]):
            is_exception = site_exc.get(host) == "block"
            row = self._make_tracker_row(
                host, count, is_blocked=False, is_exception=is_exception
            )
            layout.addWidget(row)

        self._content_layout.addWidget(box)

    def _make_tracker_row(self, host, count, is_blocked, is_exception):
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ border-bottom: 1px solid {style.BORDER}; }}"
            f"QFrame:last-child {{ border-bottom: none; }}"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 6, 4, 6)
        h.setSpacing(8)

        # Status dot
        dot_color = style.RED if is_blocked else style.GREEN
        dot = QLabel("\u25CF")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 10px;")
        dot.setFixedWidth(14)
        h.addWidget(dot)

        # Domain
        domain_label = QLabel(host)
        domain_label.setStyleSheet(f"font-size: 12px; color: {style.TEXT};")
        h.addWidget(domain_label, 1)

        # Request count
        count_label = QLabel(f"{count}")
        count_label.setStyleSheet(f"font-size: 11px; color: {style.TEXT_FAINT};")
        count_label.setToolTip(f"{count} request{'s' if count != 1 else ''}")
        h.addWidget(count_label)

        # Action button
        if is_blocked:
            btn = QPushButton("Allow here")
            btn.setStyleSheet(style.PRIVACY_ROW_BTN)
            btn.setToolTip(f"Allow {host} on this site only")
            btn.clicked.connect(lambda _, h=host: self._set_exception(h, "allow"))
        else:
            btn = QPushButton("Block here")
            btn.setStyleSheet(style.PRIVACY_ROW_BTN)
            btn.setToolTip(f"Block {host} on this site only")
            btn.clicked.connect(lambda _, h=host: self._set_exception(h, "block"))

        # If there's already an exception, show an undo button instead
        exc = storage.load_site_exceptions().get(self._site_host, {}).get(host)
        if exc:
            btn.setText(f"Undo ({exc})")
            btn.setToolTip(f"Remove the per-site '{exc}' exception for {host}")
            btn.clicked.connect(lambda _, h=host: None)  # disconnect above
            btn.disconnect()
            btn.clicked.connect(lambda _, h=host: self._remove_exception(h))

        h.addWidget(btn)
        return row

    def _set_exception(self, tracker_host, action):
        storage.set_site_exception(self._site_host, tracker_host, action)
        self._mw._adblocker.set_site_exceptions(storage.load_site_exceptions())
        self._needs_reload = True
        self._reload_hint.setText("Reload page for changes to take effect")
        self._refresh()

    def _remove_exception(self, tracker_host):
        storage.remove_site_exception(self._site_host, tracker_host)
        self._mw._adblocker.set_site_exceptions(storage.load_site_exceptions())
        self._needs_reload = True
        self._reload_hint.setText("Reload page for changes to take effect")
        self._refresh()

    # ── cookie section ───────────────────────────────────────────

    def _add_cookie_section(self):
        cookies_by_domain: dict[str, int] = {}
        for cookie in self._mw._all_cookies:
            domain = cookie.domain().lstrip(".")
            cookies_by_domain[domain] = cookies_by_domain.get(domain, 0) + 1

        # Split first-party vs third-party
        fp_cookies = {}
        tp_cookies = {}
        site = self._site_host.removeprefix("www.")
        for domain, count in cookies_by_domain.items():
            clean = domain.removeprefix("www.")
            if clean == site or clean.endswith("." + site) or site.endswith("." + clean):
                fp_cookies[domain] = count
            else:
                tp_cookies[domain] = count

        fp_total = sum(fp_cookies.values())
        tp_total = sum(tp_cookies.values())

        self._add_section_header(
            f"Cookies  ({fp_total} first-party \u00b7 {tp_total} third-party)"
        )

        box = self._make_section_box()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)

        if not fp_cookies and not tp_cookies:
            empty = QLabel("No cookies stored for this site.")
            empty.setStyleSheet(f"color: {style.TEXT_FAINT}; font-size: 12px; padding: 8px 0;")
            layout.addWidget(empty)
            self._content_layout.addWidget(box)
            return

        # First-party cookies
        for domain, count in sorted(fp_cookies.items()):
            row = self._make_cookie_row(domain, count, is_first_party=True)
            layout.addWidget(row)

        # Third-party cookies
        for domain, count in sorted(tp_cookies.items()):
            row = self._make_cookie_row(domain, count, is_first_party=False)
            layout.addWidget(row)

        # Delete all third-party button
        if tp_cookies:
            btn_row = QFrame()
            btn_layout = QHBoxLayout(btn_row)
            btn_layout.setContentsMargins(4, 8, 4, 4)
            btn_layout.addStretch()
            del_tp_btn = QPushButton(f"Delete all third-party ({tp_total})")
            del_tp_btn.setStyleSheet(style.PRIVACY_ROW_BTN_DANGER)
            del_tp_btn.clicked.connect(
                lambda: self._delete_third_party_cookies(list(tp_cookies.keys()))
            )
            btn_layout.addWidget(del_tp_btn)
            layout.addWidget(btn_row)

        self._content_layout.addWidget(box)

    def _make_cookie_row(self, domain, count, is_first_party):
        row = QFrame()
        row.setStyleSheet(f"QFrame {{ border-bottom: 1px solid {style.BORDER}; }}")
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 6, 4, 6)
        h.setSpacing(8)

        dot_color = style.GREEN if is_first_party else style.YELLOW
        dot = QLabel("\u25CF")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 10px;")
        dot.setFixedWidth(14)
        h.addWidget(dot)

        domain_label = QLabel(domain)
        domain_label.setStyleSheet(f"font-size: 12px; color: {style.TEXT};")
        h.addWidget(domain_label, 1)

        count_label = QLabel(f"{count}")
        count_label.setStyleSheet(f"font-size: 11px; color: {style.TEXT_FAINT};")
        h.addWidget(count_label)

        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet(style.PRIVACY_ROW_BTN_DANGER)
        del_btn.clicked.connect(lambda _, d=domain: self._delete_cookies(d))
        h.addWidget(del_btn)
        return row

    def _delete_cookies(self, domain):
        self._mw._delete_cookies_for_domain(domain)
        self._refresh()

    def _delete_third_party_cookies(self, domains):
        for domain in domains:
            self._mw._delete_cookies_for_domain(domain)
        self._refresh()

    # ── permissions section ───────────────────────────────────────

    def _add_permission_section(self):
        all_perms = storage.load_permissions()
        site_perms = all_perms.get(self._site_host, {})

        self._add_section_header(
            f"Permissions  ({len(site_perms)} set)"
        )

        box = self._make_section_box()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)

        if not site_perms:
            empty = QLabel("No permissions granted or denied for this site.")
            empty.setStyleSheet(f"color: {style.TEXT_FAINT}; font-size: 12px; padding: 8px 0;")
            layout.addWidget(empty)
            self._content_layout.addWidget(box)
            return

        friendly_names = {
            "geolocation": "Geolocation",
            "microphone": "Microphone",
            "camera": "Camera",
            "camera_microphone": "Camera + Mic",
            "notifications": "Notifications",
            "screen_share": "Screen Share",
            "screen_share_audio": "Screen + Audio",
        }

        for feature, decision in sorted(site_perms.items()):
            row = QFrame()
            row.setStyleSheet(f"QFrame {{ border-bottom: 1px solid {style.BORDER}; }}")
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 6, 4, 6)
            h.setSpacing(8)

            color = style.GREEN if decision == "allow" else style.RED
            dot = QLabel("\u25CF")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            dot.setFixedWidth(14)
            h.addWidget(dot)

            name = friendly_names.get(feature, feature.replace("_", " ").title())
            name_label = QLabel(name)
            name_label.setStyleSheet(f"font-size: 12px; color: {style.TEXT};")
            h.addWidget(name_label, 1)

            status_label = QLabel(decision.title())
            status_label.setStyleSheet(f"font-size: 11px; color: {color};")
            h.addWidget(status_label)

            revoke_btn = QPushButton("Revoke")
            revoke_btn.setStyleSheet(style.PRIVACY_ROW_BTN_DANGER)
            revoke_btn.clicked.connect(
                lambda _, f=feature: self._revoke_permission(f)
            )
            h.addWidget(revoke_btn)
            layout.addWidget(row)

        self._content_layout.addWidget(box)

    def _revoke_permission(self, feature):
        storage.remove_permission(self._site_host, feature)
        self._refresh()

    # ── tracking params section ──────────────────────────────────

    def _add_tracking_params_section(self):
        page_data = self._mw._adblocker.get_page_data(self._site_host)
        params = sorted(page_data.stripped_params) if page_data else []

        if not params:
            return

        self._add_section_header(
            f"Tracking Parameters Stripped  ({len(params)})"
        )

        box = self._make_section_box()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # Show as tags
        flow = QHBoxLayout()
        flow.setSpacing(6)
        for param in params:
            tag = QLabel(param)
            tag.setStyleSheet(
                f"background: {style.BG_MID}; color: {style.YELLOW}; "
                f"font-size: 11px; font-family: monospace; "
                f"padding: 3px 8px; border-radius: 4px; "
                f"border: 1px solid {style.BORDER};"
            )
            flow.addWidget(tag)
        flow.addStretch()
        layout.addLayout(flow)

        self._content_layout.addWidget(box)

    # ── helpers ───────────────────────────────────────────────────

    def _add_section_header(self, text):
        label = QLabel(text)
        label.setStyleSheet(style.PRIVACY_SECTION_HEADER)
        self._content_layout.addWidget(label)

    def _make_section_box(self):
        box = QFrame()
        box.setStyleSheet(style.PRIVACY_SECTION_BOX)
        return box

    def _refresh(self):
        """Rebuild the panel content."""
        # Clear existing content
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._populate()
