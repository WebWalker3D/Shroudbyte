import json
import os
import sys
import time
from functools import partial

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QApplication

from browser import storage, style
from browser.pwa import install_pwa, uninstall_pwa


class PageFeaturesMixin:
    """Page Watcher, Link Intelligence, Form Drafts, Bookmarks, and PWA support."""

    # ------------------------------------------------------------------
    # Page Watcher
    # ------------------------------------------------------------------

    def _add_page_watch(self, view):
        url = view.url().toString()
        title = view.title() or url
        interval = self._settings.get("page_watch_interval", 3600)
        if storage.add_watch(url, title, interval):
            self._page_watcher.reload_watches()
            self._status.showMessage(f"Watching: {title[:60]}", 4000)
            self._update_watch_indicator()

    def _remove_page_watch(self, view):
        url = view.url().toString()
        storage.remove_watch(url)
        self._page_watcher.reload_watches()
        self._status.showMessage("Stopped watching this page", 4000)
        self._update_watch_indicator()

    def _on_page_watch_changed(self, watch_data):
        """Handle a page change detected by the watcher."""
        from PyQt6.QtWidgets import QSystemTrayIcon
        if not hasattr(self, "_tray_icon"):
            self._tray_icon = QSystemTrayIcon(self)
            self._tray_icon.setVisible(True)
        title = watch_data.get("title", "")[:60]
        if self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(
                "Page Changed",
                f"{title} has been updated",
                QSystemTrayIcon.MessageIcon.Information, 5000,
            )
        self._status.showMessage(f"Page changed: {title}", 8000)

    def _handle_watch_action(self, data):
        """Process actions from the shroud://watches page."""
        action = data.get("action", "")
        url = data.get("url", "")

        if action == "remove" and url:
            storage.remove_watch(url)
            self._page_watcher.reload_watches()
        elif action == "toggle" and url:
            watches = storage.load_watches()
            for w in watches:
                if w["url"] == url:
                    w["enabled"] = not w["enabled"]
                    break
            storage.save_watches(watches)
            self._page_watcher.reload_watches()
        elif action == "check_now" and url:
            self._page_watcher.check_now(url)
        elif action == "set_interval" and url:
            interval = int(data.get("interval", 3600))
            storage.update_watch(url, {"interval": interval})
            self._page_watcher.reload_watches()
        self._update_watch_indicator()

    def _update_watch_indicator(self):
        watches = storage.load_watches()
        active = sum(1 for w in watches if w.get("enabled", True))
        if active > 0:
            self._watch_label.setText(f"  {active} watched")
            self._watch_label.setStyleSheet(style.WATCH_LABEL_STYLE)
            self._watch_label.setVisible(True)
        else:
            self._watch_label.setVisible(False)

    # ------------------------------------------------------------------
    # Link Intelligence
    # ------------------------------------------------------------------

    def _handle_link_hover(self, href, view):
        """Called from ShroudPage when the user hovers a link."""
        if not self._settings.get("link_intelligence", True):
            return
        if not view:
            return

        def _callback(result):
            # Emit signal — safe from any thread; Qt queues it to the GUI thread.
            self._link_resolved_sig.emit(result, view)

        self._link_resolver.resolve(href, _callback)

    def _on_link_resolved(self, result, view):
        """Deliver resolved link data back to the page JS."""
        if not view or not view.page():
            return
        # Verify the view is still a live tab
        found = False
        for i in range(self._tabs.count()):
            if self._tabs.widget(i) is view:
                found = True
                break
        if not found:
            return
        view.page().runJavaScript(
            f"window.__shroudShowLinkIntel&&window.__shroudShowLinkIntel({json.dumps(result)})"
        )

    def _get_link_intel_js(self):
        """Return JS that enables Link Intelligence hover tooltips."""
        return """(function() {
    if (window.__shroudLinkIntel) return;
    window.__shroudLinkIntel = true;

    var tip = document.createElement('div');
    tip.id = 'shroud-link-intel';
    tip.style.cssText =
        'position:fixed;z-index:2147483647;max-width:420px;padding:0;' +
        'background:#14131a;border:1px solid #282633;border-radius:10px;' +
        'box-shadow:0 8px 32px rgba(0,0,0,0.6);font-family:-apple-system,Cantarell,sans-serif;' +
        'font-size:12px;color:#ede8e3;pointer-events:none;opacity:0;display:none;' +
        'transition:opacity 0.15s ease;overflow:hidden;border-left:3px solid #7db88f;';
    document.documentElement.appendChild(tip);

    var styleEl = document.createElement('style');
    styleEl.textContent = '@keyframes shroudPulse{0%,100%{opacity:.3}50%{opacity:1}}';
    document.documentElement.appendChild(styleEl);

    var timer = null, currentHref = null, lastRect = null;

    function esc(s) { var d = document.createElement('span'); d.textContent = s; return d.innerHTML; }
    function domain(u) { try { return new URL(u).hostname; } catch(e) { return u; } }

    function position() {
        if (!lastRect) return;
        tip.style.display = 'block';
        var tw = tip.offsetWidth, th = tip.offsetHeight;
        var x = lastRect.left, y = lastRect.bottom + 8;
        if (x + tw > window.innerWidth - 12) x = window.innerWidth - tw - 12;
        if (x < 12) x = 12;
        if (y + th > window.innerHeight - 12) y = lastRect.top - th - 8;
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
    }

    function showResult(data) {
        if (data.href !== currentHref) return;

        var r = data.redirects || 0;
        var t = data.trackers ? data.trackers.length : 0;
        var tp = data.tracking_params ? data.tracking_params.length : 0;
        var short = data.shortener;

        var sev = 'clean';
        if (t > 0) sev = 'danger';
        else if (r > 0 || tp > 0 || short) sev = 'warn';

        var borderColor = {clean:'#7db88f', warn:'#d4a857', danger:'#d96b6b'}[sev];
        tip.style.borderLeftColor = borderColor;

        var badge = {
            clean: {bg:'#122118',fg:'#7db88f',text:'\\u2713 Direct'},
            warn:  {bg:'#2a2210',fg:'#d4a857',text:'\\u21B3 ' + r + ' redirect' + (r!==1?'s':'')},
            danger:{bg:'#2a1215',fg:'#d96b6b',text:'\\u26A0 ' + t + ' tracker' + (t!==1?'s':'')}
        }[sev];

        var h = '<div style="padding:10px 14px;">';

        h += '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">';
        h += '<span style="display:inline-block;padding:2px 8px;border-radius:4px;' +
             'font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;' +
             'background:'+badge.bg+';color:'+badge.fg+';">'+badge.text+'</span>';
        if (short) h += '<span style="font-size:10px;color:#8a8494;">shortener</span>';
        if (tp > 0) h += '<span style="font-size:10px;color:#8a8494;">' +
            tp + ' tracking param' + (tp!==1?'s':'') + '</span>';
        h += '</div>';

        if (r > 0 || data.final !== data.href) {
            var finalUrl = data.final;
            if (finalUrl.length > 72) finalUrl = finalUrl.substring(0,69) + '\\u2026';
            h += '<div style="margin-top:6px;color:#cd8d6a;font-size:11px;word-break:break-all;' +
                 'font-family:monospace;">\\u2192 ' + esc(finalUrl) + '</div>';
        }

        if (r > 0 && data.chain && data.chain.length > 0) {
            h += '<div style="margin-top:6px;padding-top:6px;border-top:1px solid #282633;' +
                 'color:#5a5568;font-size:10px;">';
            var show = data.chain.slice(0, 4);
            for (var i = 0; i < show.length; i++) {
                var d = domain(show[i]);
                var isT = data.trackers && data.trackers.indexOf(d) !== -1;
                h += '<div style="padding:1px 0;' + (isT?'color:#d96b6b;':'') + '">' +
                     (i>0?'\\u2192 ':'') + esc(d) + (isT?' \\u2022 tracker':'') + '</div>';
            }
            if (data.chain.length > 4) h += '<div>+ ' + (data.chain.length-4) + ' more</div>';
            h += '<div style="padding:1px 0;">\\u2192 ' + esc(domain(data.final)) + '</div>';
            h += '</div>';
        }

        if (t > 0 && r === 0) {
            h += '<div style="margin-top:6px;padding-top:6px;border-top:1px solid #282633;' +
                 'color:#d96b6b;font-size:10px;">';
            for (var j = 0; j < data.trackers.length && j < 5; j++)
                h += '<div>\\u2022 ' + esc(data.trackers[j]) + '</div>';
            h += '</div>';
        }

        h += '</div>';
        tip.innerHTML = h;
        position();
        tip.style.opacity = '1';
    }

    window.__shroudShowLinkIntel = function(data) { showResult(data); };

    function dismiss() {
        clearTimeout(timer);
        currentHref = null;
        tip.style.opacity = '0';
        setTimeout(function() { if (!currentHref) tip.style.display = 'none'; }, 200);
    }

    // Single mouseover handler replaces both mouseover+mouseout.
    // When cursor moves between child elements of the same <a>,
    // href === currentHref so we skip (no flicker, no reset).
    document.addEventListener('mouseover', function(e) {
        var a = e.target.closest('a[href]');

        // Moved off any link — dismiss
        if (!a) { if (currentHref) dismiss(); return; }

        var href = a.href;
        if (!href) { if (currentHref) dismiss(); return; }

        // Still on the same link (moved between child elements) — no-op
        if (href === currentHref) return;

        var lc = href.toLowerCase();
        if (lc.startsWith('javascript:') || lc.startsWith('mailto:') ||
            lc.startsWith('tel:') || lc.startsWith('data:') || lc.startsWith('blob:')) return;
        if (href.indexOf('#') > 0 &&
            href.split('#')[0] === window.location.href.split('#')[0]) return;

        // New link — reset and start fresh
        clearTimeout(timer);
        currentHref = href;
        lastRect = a.getBoundingClientRect();

        timer = setTimeout(function() {
            tip.innerHTML = '<div style="padding:8px 14px;color:#5a5568;font-size:11px;">' +
                '<span style="display:inline-block;animation:shroudPulse 1s ease infinite;">\\u2022</span> ' +
                'Resolving link\\u2026</div>';
            tip.style.borderLeftColor = '#282633';
            position();
            tip.style.opacity = '1';
            console.log('__SHROUD_LINK_HOVER__:' + JSON.stringify({href:href}));
        }, 400);
    }, true);

    // Catch cursor leaving the page entirely
    document.addEventListener('mouseleave', function() { dismiss(); });
})();"""

    # ------------------------------------------------------------------
    # Form Draft Auto-Save
    # ------------------------------------------------------------------

    def _handle_form_draft(self, data):
        """Handle form draft save/dismiss from injected JS."""
        action = data.get("action", "")
        url = data.get("url", "")
        if action == "save" and url:
            fields = data.get("fields", {})
            if fields:
                storage.save_form_draft(url, fields)
        elif action == "dismiss" and url:
            storage.remove_form_draft(url)

    def _get_form_draft_js(self, draft_json):
        """Return JS that auto-saves form fields and offers draft restore."""
        return f"""(function() {{
    if (window.__shroudFormDraft) return;
    window.__shroudFormDraft = true;

    var SAVE_INTERVAL = 30000;
    var savedDraft = {draft_json};

    function getFields() {{
        var fields = {{}};
        var inputs = document.querySelectorAll('input, textarea, select');
        var hasContent = false;
        for (var i = 0; i < inputs.length; i++) {{
            var el = inputs[i];
            if (!el.name && !el.id) continue;
            var key = el.name || el.id;
            if (el.type === 'password' || el.type === 'hidden' || el.type === 'submit'
                || el.type === 'button' || el.type === 'image' || el.type === 'file') continue;
            var val;
            if (el.type === 'checkbox' || el.type === 'radio') {{
                val = el.checked;
            }} else {{
                val = el.value;
            }}
            if (val && val !== '' && val !== false) hasContent = true;
            fields[key] = val;
        }}
        return hasContent ? fields : null;
    }}

    function restoreFields(fields) {{
        for (var key in fields) {{
            var el = document.querySelector('[name="' + key + '"], #' + CSS.escape(key));
            if (!el) continue;
            if (el.type === 'checkbox' || el.type === 'radio') {{
                el.checked = !!fields[key];
            }} else {{
                el.value = fields[key] || '';
            }}
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}
    }}

    // Periodic auto-save
    setInterval(function() {{
        var fields = getFields();
        if (fields) {{
            console.log('__SHROUD_FORM_DRAFT__:' + JSON.stringify({{
                action: 'save', url: location.href, fields: fields
            }}));
        }}
    }}, SAVE_INTERVAL);

    // Also save on beforeunload
    window.addEventListener('beforeunload', function() {{
        var fields = getFields();
        if (fields) {{
            console.log('__SHROUD_FORM_DRAFT__:' + JSON.stringify({{
                action: 'save', url: location.href, fields: fields
            }}));
        }}
    }});

    // Show restore bar if draft exists
    if (savedDraft && savedDraft.fields) {{
        var ago = '';
        var diff = (Date.now() / 1000) - (savedDraft.saved || 0);
        if (diff < 60) ago = 'just now';
        else if (diff < 3600) ago = Math.floor(diff / 60) + 'm ago';
        else if (diff < 86400) ago = Math.floor(diff / 3600) + 'h ago';
        else ago = Math.floor(diff / 86400) + 'd ago';

        var bar = document.createElement('div');
        bar.style.cssText =
            'position:fixed;top:0;left:0;right:0;z-index:2147483646;' +
            'background:#14131a;border-bottom:1px solid #282633;' +
            'padding:8px 16px;display:flex;align-items:center;gap:12px;' +
            'font-family:-apple-system,Cantarell,sans-serif;font-size:13px;color:#ede8e3;' +
            'box-shadow:0 4px 16px rgba(0,0,0,0.4);';

        bar.innerHTML =
            '<span style="color:#8a8494;">Restore draft from ' + ago + '?</span>' +
            '<button id="__shroud_draft_restore" style="padding:4px 14px;font-size:12px;' +
            'background:#cd8d6a;color:#0c0b10;border:none;border-radius:6px;cursor:pointer;' +
            'font-weight:600;font-family:inherit;">Restore</button>' +
            '<button id="__shroud_draft_dismiss" style="padding:4px 14px;font-size:12px;' +
            'background:transparent;color:#5a5568;border:1px solid #282633;border-radius:6px;' +
            'cursor:pointer;font-family:inherit;">Dismiss</button>';

        document.documentElement.appendChild(bar);

        document.getElementById('__shroud_draft_restore').onclick = function() {{
            restoreFields(savedDraft.fields);
            bar.remove();
        }};
        document.getElementById('__shroud_draft_dismiss').onclick = function() {{
            console.log('__SHROUD_FORM_DRAFT__:' + JSON.stringify({{
                action: 'dismiss', url: location.href
            }}));
            bar.remove();
        }};
    }}
}})();"""

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
            added = storage.add_bookmark(title, url)
            if added:
                self._bookmark_btn.setText("\u2605")
                self._status.showMessage("Bookmark added", 2000)
            else:
                self._status.showMessage("Already bookmarked", 2000)

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

    # ------------------------------------------------------------------
    # PWA support
    # ------------------------------------------------------------------

    def _handle_pwa(self, data):
        """Handle PWA manifest detection from injected JS."""
        action = data.get("action", "")
        if action == "manifest":
            manifest = data.get("manifest", {})
            page_url = data.get("page_url", "")
            manifest_url = data.get("manifest_url", "")
            if manifest and page_url:
                # Store on current view for install action
                view = self._current_view()
                if view:
                    view._pwa_manifest = manifest
                    view._pwa_page_url = page_url
                    view._pwa_manifest_url = manifest_url

    def _install_pwa(self, view):
        """Install the current page as a PWA."""
        import threading
        from PyQt6.QtCore import QTimer

        manifest = getattr(view, '_pwa_manifest', None)
        if not manifest:
            self._status.showMessage("No web app manifest found on this page", 3000)
            return
        page_url = getattr(view, '_pwa_page_url', view.url().toString())
        manifest_url = getattr(view, '_pwa_manifest_url', '')

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def _worker():
            try:
                app_data = install_pwa(manifest, page_url, manifest_url)
                name = app_data.get("name", "App")
                QTimer.singleShot(0, lambda: self._on_pwa_installed(name))
            except Exception as exc:
                msg = str(exc)
                QTimer.singleShot(0, lambda: self._on_pwa_install_failed(msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_pwa_installed(self, name):
        QApplication.restoreOverrideCursor()
        self._status.showMessage(
            f"Installed: {name} — find it in your app launcher", 5000)

    def _on_pwa_install_failed(self, error):
        QApplication.restoreOverrideCursor()
        self._status.showMessage(f"Install failed: {error}", 5000)

    def _uninstall_pwa_action(self, start_url):
        """Uninstall a PWA by start URL."""
        uninstall_pwa(start_url)
        self._status.showMessage("App uninstalled", 3000)

    def _handle_page_action(self, data):
        """Handle actions from shroud://bookmarks and shroud://history pages."""
        action = data.get("action", "")
        arg = data.get("arg", "")

        if action == "del_bookmark" and arg:
            storage.remove_bookmark(arg)
            self._populate_bookmarks_menu()
            view = self._current_view()
            if view:
                self._update_bookmark_btn(view.url())
        elif action == "edit_bookmark" and arg:
            title = data.get("title")
            folder = data.get("folder")
            tags = data.get("tags")
            storage.update_bookmark(arg, title=title, folder=folder, tags=tags)
            self._populate_bookmarks_menu()
        elif action == "clear_history":
            storage.clear_history()
            self._status.showMessage("History cleared", 2000)
        elif action == "clear_screentime":
            storage.clear_screen_time()
            self._status.showMessage("Screen time data cleared", 2000)
        elif action == "del_saved" and arg:
            storage.remove_saved_page(arg)
            self._status.showMessage("Saved page deleted", 2000)
        elif action == "uninstall_app" and arg:
            self._uninstall_pwa_action(arg)
        elif action == "launch_app" and arg:
            import subprocess
            from pathlib import Path
            project_dir = str(Path(__file__).parent.parent)
            subprocess.Popen(
                [sys.executable, "-m", "browser", f"--app={arg}"],
                cwd=project_dir,
                start_new_session=True,
            )
        # Named session actions
        elif action == "save_session" and arg:
            from browser.session_manager import save_named_session
            tabs = []
            for i in range(self._tabs.count()):
                view = self._tabs.widget(i)
                if view:
                    deferred = getattr(view, "_deferred_url", None)
                    url = deferred or view.url().toString()
                    title = view.title() or self._tabs.tabText(i)
                    if url and not url.startswith("shroud:"):
                        tabs.append({"url": url, "title": title})
            save_named_session(arg, tabs)
            self._status.showMessage(f"Session saved: {arg}", 3000)
        elif action == "load_session" and arg:
            from browser.session_manager import load_named_session
            tabs = load_named_session(arg)
            if tabs:
                for tab_info in tabs:
                    url = tab_info.get("url", "")
                    if url:
                        self.add_new_tab(QUrl(url))
                self._status.showMessage(
                    f"Loaded session: {arg} ({len(tabs)} tabs)", 3000
                )
            else:
                self._status.showMessage(f"Session '{arg}' is empty", 2000)
        elif action == "delete_session" and arg:
            from browser.session_manager import delete_session
            delete_session(arg)
            storage.invalidate_cache("named_sessions.json")
            self._status.showMessage(f"Session deleted: {arg}", 2000)
        # WARC capture actions
        elif action == "save_wacz":
            if hasattr(self, "_warc_capture") and self._warc_capture.record_count > 0:
                title = self._current_view().title() if self._current_view() else ""
                cap_path = os.path.expanduser(f"~/capture_{int(time.time())}.wacz")
                self._warc_capture.save_wacz(cap_path, title)
                self._status.showMessage(f"Saved WACZ to {os.path.basename(cap_path)}", 3000)
        elif action == "save_warc":
            if hasattr(self, "_warc_capture") and self._warc_capture.record_count > 0:
                cap_path = os.path.expanduser(f"~/capture_{int(time.time())}.warc")
                self._warc_capture.save_warc(cap_path)
                self._status.showMessage(f"Saved WARC to {os.path.basename(cap_path)}", 3000)
        elif action == "clear_capture":
            if hasattr(self, "_warc_capture"):
                self._warc_capture.stop()
                self._warc_capture._records = []
                self._warc_capture._urls = []
                self._capture_btn.setText("\u23fa")
                self._capture_btn.setToolTip("Start WARC Capture")
                self._capture_btn.setStyleSheet(style.NAV_BTN_STYLE)
                self._status.showMessage("Capture data cleared", 2000)
        # Background activity actions
        elif action == "pause_worker" and arg:
            if hasattr(self, "_bg_activity"):
                self._bg_activity.pause_worker(arg)
                self._status.showMessage(f"Paused worker for {arg}", 2000)
        elif action == "resume_worker" and arg:
            if hasattr(self, "_bg_activity"):
                self._bg_activity.resume_worker(arg)
                self._status.showMessage(f"Resumed worker for {arg}", 2000)
        elif action == "unregister_worker" and arg:
            if hasattr(self, "_bg_activity"):
                self._bg_activity.unregister_service_worker(arg)
                self._status.showMessage(f"Unregistered worker for {arg}", 2000)
        elif action == "revoke_push" and arg:
            if hasattr(self, "_bg_activity"):
                self._bg_activity.revoke_push_subscription(arg)
                self._status.showMessage(f"Revoked push subscription for {arg}", 2000)
        # Profile/container actions
        elif action == "add_profile" and arg:
            if hasattr(self, "_profile_manager"):
                color = data.get("color", "#6366f1")
                self._profile_manager.add_profile(arg, color=color)
                self._status.showMessage(f"Profile created: {arg}", 2000)
        elif action == "remove_profile" and arg:
            if hasattr(self, "_profile_manager"):
                self._profile_manager.remove_profile(arg)
                self._status.showMessage(f"Profile removed: {arg}", 2000)
        elif action == "update_profile" and arg:
            if hasattr(self, "_profile_manager"):
                color = data.get("color")
                auto_assign = data.get("auto_assign")
                self._profile_manager.update_profile(
                    arg, color=color, auto_assign=auto_assign)
                self._status.showMessage(f"Profile updated: {arg}", 2000)
        # Extension actions
        elif action == "reload_extensions":
            if hasattr(self, "_extension_manager"):
                self._extension_manager.reload()
                count = len(self._extension_manager.get_extensions())
                self._status.showMessage(
                    f"Extensions reloaded: {count} found", 2000)
        elif action == "enable_ext" and arg:
            if hasattr(self, "_extension_manager"):
                self._extension_manager.enable(arg)
                self._status.showMessage(f"Extension enabled: {arg}", 2000)
        elif action == "disable_ext" and arg:
            if hasattr(self, "_extension_manager"):
                self._extension_manager.disable(arg)
                self._status.showMessage(f"Extension disabled: {arg}", 2000)

    # ------------------------------------------------------------------
    # WARC/WACZ Capture
    # ------------------------------------------------------------------

    def _toggle_capture(self):
        """Toggle WARC capture on/off."""
        if self._warc_capture.is_active:
            self._warc_capture.stop()
            self._capture_btn.setText("\u23fa")
            self._capture_btn.setToolTip("Start WARC Capture")
            self._capture_btn.setStyleSheet(style.NAV_BTN_STYLE)
            self._status.showMessage(
                f"Capture stopped \u2014 {self._warc_capture.record_count} records", 3000
            )
        else:
            url = self._current_view().url().toString() if self._current_view() else ""
            self._warc_capture.start(url)
            self._capture_btn.setText("\u23f9")
            self._capture_btn.setToolTip("Stop WARC Capture")
            self._capture_btn.setStyleSheet(
                style.NAV_BTN_STYLE.replace("}", "color: #ef4444;}")
            )
            self._status.showMessage("WARC capture started", 2000)

    def _save_warc_capture(self):
        """Save the current capture as WARC or WACZ."""
        if self._warc_capture.record_count == 0:
            self._status.showMessage("No capture data to save", 2000)
            return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Capture",
            os.path.expanduser(f"~/capture_{int(time.time())}.wacz"),
            "WACZ Archive (*.wacz);;WARC File (*.warc)",
        )
        if not path:
            return
        if path.endswith(".warc"):
            self._warc_capture.save_warc(path)
        else:
            title = self._current_view().title() if self._current_view() else ""
            self._warc_capture.save_wacz(path, title)
        self._status.showMessage(f"Capture saved to {os.path.basename(path)}", 3000)

    def _show_bookmarks(self):
        view = self._current_view()
        if view:
            view.load(QUrl("shroud://bookmarks"))
        else:
            self.add_new_tab(QUrl("shroud://bookmarks"))
