"""Password manager UI dialogs for Shroudbyte."""

import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QFormLayout,
)

from . import style
from .passwords import PasswordVault


class MasterPasswordDialog(QDialog):
    """Prompt user for master password (setup or unlock).

    When *keyring_available* is True and the vault is being set up for the
    first time, an "Use OS keyring" checkbox is shown, letting the user
    skip the master password entirely.
    """

    def __init__(self, vault: PasswordVault, parent=None, keyring_available: bool = False):
        super().__init__(parent)
        self._vault = vault
        self._is_setup = not vault.is_setup() and not vault.is_keyring_setup()
        self._chosen_backend = "master_password"
        self.setWindowTitle("Set Master Password" if self._is_setup else "Unlock Password Vault")
        self.setMinimumWidth(400)
        self.setStyleSheet(style.PASSWORD_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # --- Keyring option (first-time setup only) ---
        self._keyring_check = None
        if self._is_setup and keyring_available:
            info = QLabel("Choose how to protect your saved credentials.")
            info.setWordWrap(True)
            layout.addWidget(info)

            self._keyring_check = QCheckBox("Use OS keyring (no password needed)")
            self._keyring_check.setToolTip(
                "Store the encryption key in your system login keyring\n"
                "(GNOME Keyring, KDE Wallet, etc.)"
            )
            self._keyring_check.toggled.connect(self._on_keyring_toggled)
            layout.addWidget(self._keyring_check)
        elif self._is_setup:
            info = QLabel("Choose a master password to protect your saved credentials.")
            info.setWordWrap(True)
            layout.addWidget(info)

        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_edit.setPlaceholderText("Master password")
        layout.addWidget(self._pw_edit)

        self._confirm_edit = None
        if self._is_setup:
            self._confirm_edit = QLineEdit()
            self._confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._confirm_edit.setPlaceholderText("Confirm master password")
            layout.addWidget(self._confirm_edit)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {style.RED}; font-size: 12px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        self._ok_btn = QPushButton("Set Password" if self._is_setup else "Unlock")
        self._ok_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        self._ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)
        self._pw_edit.returnPressed.connect(self._on_ok)
        if self._is_setup:
            self._confirm_edit.returnPressed.connect(self._on_ok)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self._ok_btn)
        layout.addLayout(btn_layout)

    def _on_keyring_toggled(self, checked: bool):
        self._pw_edit.setEnabled(not checked)
        self._pw_edit.setVisible(not checked)
        if self._confirm_edit:
            self._confirm_edit.setEnabled(not checked)
            self._confirm_edit.setVisible(not checked)
        self._ok_btn.setText("Create Vault" if checked else "Set Password")
        self._error_label.setVisible(False)

    @property
    def chosen_backend(self) -> str:
        return self._chosen_backend

    def _on_ok(self):
        # Keyring mode — no password needed
        if self._keyring_check and self._keyring_check.isChecked():
            try:
                self._vault.setup_with_keyring()
                self._chosen_backend = "keyring"
                self.accept()
            except Exception as exc:
                self._show_error(f"Keyring setup failed: {exc}")
            return

        pw = self._pw_edit.text()
        if not pw:
            self._show_error("Password cannot be empty.")
            return

        if self._is_setup:
            if pw != self._confirm_edit.text():
                self._show_error("Passwords do not match.")
                return
            if len(pw) < 8:
                self._show_error("Password must be at least 8 characters.")
                return
            self._vault.setup(pw)
            self._chosen_backend = "master_password"
            self.accept()
        else:
            if self._vault.unlock(pw):
                self._chosen_backend = "master_password"
                self.accept()
            else:
                self._show_error("Wrong password.")

    def _show_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.setVisible(True)


class PasswordManagerDialog(QDialog):
    """Main password manager dialog — list, search, add, edit, delete entries."""

    def __init__(self, vault: PasswordVault, parent=None):
        super().__init__(parent)
        self._vault = vault
        self.setWindowTitle("Password Manager")
        self.setMinimumSize(640, 480)
        self.setStyleSheet(style.PASSWORD_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("  Search passwords...")
        self._search.setStyleSheet(style.SEARCH_INPUT_STYLE)
        self._search.textChanged.connect(self._populate)
        layout.addWidget(self._search)

        # List
        self._listw = QListWidget()
        self._listw.setStyleSheet(style.LIST_WIDGET_STYLE)
        layout.addWidget(self._listw)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        add_btn = QPushButton("Add")
        add_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        add_btn.clicked.connect(self._add_entry)

        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        edit_btn.clicked.connect(self._edit_entry)

        copy_user_btn = QPushButton("Copy User")
        copy_user_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        copy_user_btn.clicked.connect(self._copy_username)

        copy_pass_btn = QPushButton("Copy Pass")
        copy_pass_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        copy_pass_btn.clicked.connect(self._copy_password)

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(style.DIALOG_BTN_DANGER_STYLE)
        delete_btn.clicked.connect(self._delete_entry)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        close_btn.clicked.connect(self.close)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(copy_user_btn)
        btn_layout.addWidget(copy_pass_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._populate()

    def _populate(self, filter_text=""):
        self._listw.clear()
        ft = filter_text.lower()
        for entry in self._vault.get_all_entries():
            name = entry.get("name", "")
            url = entry.get("site_url", "")
            user = entry.get("username", "")
            if ft and ft not in name.lower() and ft not in url.lower() and ft not in user.lower():
                continue
            display = f"{name}\n{user}  —  {url}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self._listw.addItem(item)

    def _selected_entry(self):
        item = self._listw.currentItem()
        if not item:
            return None
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        for e in self._vault.get_all_entries():
            if e["id"] == entry_id:
                return e
        return None

    def _add_entry(self):
        dlg = _PasswordEntryDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self._vault.add_entry(data["site_url"], data["username"], data["password"], data["name"])
            self._populate(self._search.text())

    def _edit_entry(self):
        entry = self._selected_entry()
        if not entry:
            return
        dlg = _PasswordEntryDialog(entry=entry, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self._vault.update_entry(
                entry["id"],
                site_url=data["site_url"],
                username=data["username"],
                password=data["password"],
                name=data["name"],
            )
            self._populate(self._search.text())

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard and auto-clear after 30 seconds."""
        from PyQt6.QtCore import QTimer
        QApplication.clipboard().setText(text)
        QTimer.singleShot(30_000, lambda: (
            QApplication.clipboard().clear()
            if QApplication.clipboard().text() == text else None
        ))

    def _copy_username(self):
        entry = self._selected_entry()
        if entry:
            self._copy_to_clipboard(entry["username"])

    def _copy_password(self):
        entry = self._selected_entry()
        if entry:
            self._copy_to_clipboard(entry["password"])

    def _delete_entry(self):
        entry = self._selected_entry()
        if not entry:
            return
        reply = QMessageBox.question(
            self, "Delete Password",
            f"Delete saved password for {entry.get('name', '')}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._vault.remove_entry(entry["id"])
            self._populate(self._search.text())


class _PasswordEntryDialog(QDialog):
    """Add/edit a single password entry."""

    def __init__(self, entry=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Password" if entry else "Add Password")
        self.setMinimumWidth(420)
        self.setStyleSheet(style.PASSWORD_DIALOG_STYLE)

        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        self._name_edit = QLineEdit(entry.get("name", "") if entry else "")
        self._name_edit.setPlaceholderText("e.g. GitHub")
        self._url_edit = QLineEdit(entry.get("site_url", "") if entry else "")
        self._url_edit.setPlaceholderText("https://example.com")
        self._user_edit = QLineEdit(entry.get("username", "") if entry else "")
        self._user_edit.setPlaceholderText("username or email")
        self._pass_edit = QLineEdit(entry.get("password", "") if entry else "")
        self._pass_edit.setPlaceholderText("password")
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)

        # Toggle password visibility
        self._show_pass_btn = QPushButton("Show")
        self._show_pass_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        self._show_pass_btn.setFixedWidth(60)
        self._show_pass_btn.clicked.connect(self._toggle_password_visibility)

        pass_layout = QHBoxLayout()
        pass_layout.setSpacing(6)
        pass_layout.addWidget(self._pass_edit)
        pass_layout.addWidget(self._show_pass_btn)

        layout.addRow("Name", self._name_edit)
        layout.addRow("URL", self._url_edit)
        layout.addRow("Username", self._user_edit)
        layout.addRow("Password", pass_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addRow(btn_layout)

    def _toggle_password_visibility(self):
        if self._pass_edit.echoMode() == QLineEdit.EchoMode.Password:
            self._pass_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_pass_btn.setText("Hide")
        else:
            self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_pass_btn.setText("Show")

    def get_data(self) -> dict:
        return {
            "name": self._name_edit.text().strip(),
            "site_url": self._url_edit.text().strip(),
            "username": self._user_edit.text().strip(),
            "password": self._pass_edit.text(),
        }


class HttpAuthDialog(QDialog):
    """Prompt for HTTP Basic/Digest authentication (401 challenges)."""

    def __init__(self, url: str, realm: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setMinimumWidth(420)
        self.setStyleSheet(style.PASSWORD_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        info = QLabel(f"The site at <b>{url}</b> requires authentication.")
        if realm:
            info.setText(info.text() + f"<br>Realm: <i>{realm}</i>")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {style.TEXT}; font-size: 13px;")
        layout.addWidget(info)

        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("Username")
        layout.addWidget(self._user_edit)

        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_edit.setPlaceholderText("Password")
        layout.addWidget(self._pass_edit)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        ok_btn = QPushButton("Log In")
        ok_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(style.DIALOG_BTN_STYLE)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        self._user_edit.returnPressed.connect(lambda: self._pass_edit.setFocus())
        self._pass_edit.returnPressed.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def credentials(self) -> tuple:
        """Return (username, password)."""
        return self._user_edit.text(), self._pass_edit.text()


class PasswordSaveBar(QFrame):
    """Notification bar shown when a login form is detected with new credentials."""

    def __init__(self, site_url: str, username: str, on_save, on_dismiss, parent=None):
        super().__init__(parent)
        self.setStyleSheet(style.PASSWORD_SAVE_BAR_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        label = QLabel(f"Save password for {username} on {site_url}?")
        label.setStyleSheet(f"color: {style.TEXT}; font-size: 13px;")

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(style.DIALOG_BTN_PRIMARY_STYLE)
        save_btn.setFixedHeight(30)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setStyleSheet(style.DIALOG_BTN_STYLE)
        dismiss_btn.setFixedHeight(30)

        save_btn.clicked.connect(lambda: (on_save(), self._remove()))
        dismiss_btn.clicked.connect(lambda: (on_dismiss(), self._remove()))

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(save_btn)
        layout.addWidget(dismiss_btn)

    def _remove(self):
        self.setParent(None)
        self.deleteLater()
