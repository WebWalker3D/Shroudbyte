from PyQt6.QtCore import Qt, QUrl, QEvent
from PyQt6.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QHBoxLayout,
)

from browser import storage, style
from browser.passwords import PasswordVault
from browser.passworddialogs import (
    MasterPasswordDialog, PasswordManagerDialog,
    PasswordSaveBar, AutofillBar,
)
import json


class PasswordMixin:
    # ------------------------------------------------------------------
    # Password manager
    # ------------------------------------------------------------------

    def _reset_vault_lock_timer(self):
        """Reset the vault auto-lock countdown."""
        mins = self._settings.get("vault_auto_lock_minutes", 15)
        if mins > 0 and self._vault.is_unlocked:
            self._vault_lock_timer.start(mins * 60 * 1000)
        else:
            self._vault_lock_timer.stop()

    def _auto_lock_vault(self):
        """Lock the password vault after idle timeout."""
        if self._vault.is_unlocked:
            self._vault.lock()
            self._status.showMessage("Password vault locked (idle timeout)", 4000)

    def event(self, event):
        """Reset vault lock timer on user interaction."""
        etype = event.type()
        if etype in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress):
            if self._vault.is_unlocked:
                self._reset_vault_lock_timer()
        return super().event(event)

    def _ensure_vault_unlocked(self) -> bool:
        """Prompt for master password if needed. Returns True if vault is unlocked."""
        if self._vault.is_unlocked:
            return True

        from browser import keyring_backend

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
        """After page load, detect login forms and watch for dynamically added ones."""
        view = self._current_view()
        if not view:
            return
        url = view.url().toString()
        if url.startswith("shroud:"):
            return
        # Inject JS that:
        # 1. Defines the credential capture helpers and form-submit hooks
        # 2. Installs them immediately if password fields exist
        # 3. Uses a MutationObserver to install hooks when password fields
        #    appear later (SPA / dynamically revealed login forms)
        js = """
        (function() {
            if (window.__shroudPasswordObserver) return 0;

            var __shroudAlert = window.alert.bind(window);
            window.__shroudCapturedCreds = null;

            function __shroudCapture(username, password) {
                var creds = {
                    username: username,
                    password: password,
                    url: window.location.href
                };
                window.__shroudCapturedCreds = creds;
                try {
                    sessionStorage.setItem('__shroud_creds', JSON.stringify(creds));
                } catch(e) {}
                try {
                    __shroudAlert("__SHROUD_CRED_CAPTURE__:" + JSON.stringify(creds));
                } catch(e) {}
            }

            function __shroudFindUsername(pw, scope) {
                var inputs = Array.from(scope.querySelectorAll('input'));
                var pwIdx = inputs.indexOf(pw);
                for (var i = pwIdx - 1; i >= 0; i--) {
                    var t = inputs[i].type;
                    if ((t === 'text' || t === 'email' || t === '') && inputs[i].value) {
                        return inputs[i].value;
                    }
                }
                return '';
            }

            function __shroudInstallHooks() {
                if (window.__shroudPasswordHooked) return;
                var pwInputs = document.querySelectorAll('input[type="password"]');
                var visible = 0;
                pwInputs.forEach(function(i) { if (i.offsetParent !== null) visible++; });
                if (visible === 0) return;

                window.__shroudPasswordHooked = true;

                document.addEventListener('submit', function(e) {
                    var form = e.target;
                    var pw = form.querySelector('input[type="password"]');
                    if (!pw || !pw.value) return;
                    __shroudCapture(__shroudFindUsername(pw, form), pw.value);
                }, true);

                document.addEventListener('click', function(e) {
                    var btn = e.target.closest(
                        'button, input[type="submit"], [role="button"]'
                    );
                    if (!btn) return;
                    if (btn.closest('form')) return;

                    var pwAll = document.querySelectorAll('input[type="password"]');
                    pwAll.forEach(function(pw) {
                        if (!pw.value) return;
                        var container = pw.closest('div, section, main, body');
                        if (!container) return;
                        __shroudCapture(__shroudFindUsername(pw, container), pw.value);
                    });
                }, true);

                return visible;
            }

            // Try immediately
            var found = __shroudInstallHooks();
            if (found) return found;

            // Watch for password fields appearing later
            window.__shroudPasswordObserver = new MutationObserver(function() {
                if (window.__shroudPasswordHooked) {
                    window.__shroudPasswordObserver.disconnect();
                    return;
                }
                if (__shroudInstallHooks()) {
                    // Notify Python that password fields were found dynamically
                    try { __shroudAlert("__SHROUD_PW_FIELDS_FOUND__"); } catch(e) {}
                }
            });
            window.__shroudPasswordObserver.observe(document.documentElement, {
                childList: true, subtree: true, attributes: true,
                attributeFilter: ['type', 'style', 'class', 'hidden']
            });
            return 0;
        })();
        """
        view.page().runJavaScript(js, lambda count: self._on_password_fields_detected(count, url))

    def _on_password_fields_detected(self, count, url):
        if count and count > 0:
            self._offer_autofill_if_available(url)

    def _on_dynamic_password_fields_found(self):
        """Called when the MutationObserver detects dynamically added password fields."""
        view = self._current_view()
        if view:
            self._offer_autofill_if_available(view.url().toString())

    def _offer_autofill_if_available(self, url):
        """Show an autofill bar if saved credentials exist for the given URL."""
        entries = self._vault.get_entries_for_url(url)
        if not entries:
            return
        entry = max(entries, key=lambda e: e.get("last_used", 0))
        username = entry["username"] or "(no username)"

        # Don't show if there's already a bar visible
        if self._autofill_bar or self._password_save_bar:
            return

        def on_fill():
            self._auto_fill_password()
            self._autofill_bar = None

        def on_dismiss():
            self._autofill_bar = None

        bar = AutofillBar(username, on_fill, on_dismiss, parent=self)
        self._autofill_bar = bar
        self._central_layout.insertWidget(0, bar)

    def _check_session_for_credentials(self):
        """After page load, check sessionStorage for creds saved by a previous page's form submit."""
        view = self._current_view()
        if not view or view.url().toString().startswith("shroud:"):
            return
        js = """
        (function() {
            try {
                var c = sessionStorage.getItem('__shroud_creds');
                if (c) {
                    sessionStorage.removeItem('__shroud_creds');
                    return JSON.parse(c);
                }
            } catch(e) {}
            return null;
        })();
        """
        view.page().runJavaScript(js, self._on_credentials_harvested)

    def _harvest_submitted_credentials(self, view=None):
        """Read credentials captured by the form submit interceptor."""
        if view is None:
            view = self._current_view()
        if not view:
            return
        page = view.page()
        # Primary: check creds stored via javaScriptAlert override (reliable)
        creds = getattr(page, '_pending_creds', None)
        if creds:
            page._pending_creds = None
            self._on_credentials_harvested(creds)
            return
        # Fallback: async JS read (may fail during cross-origin navigation)
        js = """
        (function() {
            var c = window.__shroudCapturedCreds;
            window.__shroudCapturedCreds = null;
            return c;
        })();
        """
        view.page().runJavaScript(js, self._on_credentials_harvested)

    def _harvest_pending_creds(self, view):
        """Timer callback for SPA logins that don't trigger navigation."""
        if not self._vault.is_unlocked or not view:
            return
        page = view.page()
        creds = getattr(page, '_pending_creds', None)
        if creds:
            page._pending_creds = None
            self._on_credentials_harvested(creds)

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
