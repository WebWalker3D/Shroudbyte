"""Custom shroud:// URL scheme handler for internal browser pages."""

import html as html_mod
import platform
import re
import sys

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtWebEngineCore import QWebEngineUrlScheme, QWebEngineUrlSchemeHandler

from . import __app_name__, __version__
from .newtab import generate_new_tab_html
from . import storage
from .style import (
    ACCENT, ACCENT_HOVER, ACCENT_TEXT,
    BG_DARK, BG_CARD, BG_MID, BG_HOVER, BG_ACTIVE,
    TEXT, TEXT_DIM, TEXT_FAINT, BORDER, GREEN, RED, YELLOW,
)


def register_shroud_scheme():
    """Register the shroud:// URL scheme.  Must be called before QApplication."""
    scheme = QWebEngineUrlScheme(b"shroud")
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setDefaultPort(-1)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)


# Available internal pages (name -> description).
_PAGES = {
    "newtab": "New Tab",
    "settings": "Settings",
    "bookmarks": "Bookmarks",
    "history": "History",
    "privacy": "Privacy Dashboard",
    "watches": "Page Watches",
    "screentime": "Screen Time",
    "about": "About Shroudbyte",
    "shortcuts": "Keyboard Shortcuts",
}


class ShroudSchemeHandler(QWebEngineUrlSchemeHandler):
    """Serves internal shroud:// pages."""

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self._profile = profile

    def requestStarted(self, job):
        url = job.requestUrl()
        host = url.host().lower()

        if host == "newtab":
            html = generate_new_tab_html()
        elif host == "settings":
            html = self._page_settings()
        elif host == "bookmarks":
            html = self._page_bookmarks()
        elif host == "history":
            html = self._page_history()
        elif host == "source":
            html = self._page_source()
        elif host == "privacy":
            html = self._page_privacy()
        elif host == "watches":
            html = self._page_watches()
        elif host == "screentime":
            html = self._page_screentime()
        elif host == "about":
            html = self._page_about()
        elif host == "shortcuts":
            html = self._page_shortcuts()
        else:
            html = self._page_error(url.toString())

        buf = QBuffer(parent=job)
        buf.setData(html.encode("utf-8"))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(b"text/html", buf)

    @staticmethod
    def _json_encode(s):
        import json
        return json.dumps(s)

    # ── Shared layout ─────────────────────────────────────────────

    _NAV = [
        ("settings", "\u2699", "Settings"),
        ("bookmarks", "\u2606", "Bookmarks"),
        ("history", "\u29D6", "History"),
        ("privacy", "\u26E8", "Privacy"),
        ("watches", "\u25CE", "Page Watches"),
        ("screentime", "\u231A", "Screen Time"),
        ("shortcuts", "\u2328", "Shortcuts"),
        ("about", "\u2139", "About"),
    ]

    def _wrap(self, title, active, content, extra_css="", extra_js="",
              sub_nav=None):
        """Wrap page content in the shared sidebar layout."""
        nav_items = ""
        for slug, icon, label in self._NAV:
            cls = "nav-item active" if slug == active else "nav-item"
            nav_items += (
                f'<a href="shroud://{slug}" class="{cls}">'
                f'<span class="nav-icon">{icon}</span> {label}</a>\n'
            )

        sub_nav_html = ""
        if sub_nav:
            sub_nav_html = '<div class="sub-nav">'
            for sid, label in sub_nav:
                sub_nav_html += (
                    f'<a href="#{sid}" class="nav-item sub'
                    f'{" active" if sid == sub_nav[0][0] else ""}"'
                    f' onclick="showSection(\'{sid}\',this)">'
                    f'{label}</a>\n'
                )
            sub_nav_html += '</div>'

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title} &mdash; {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; min-height: 100vh;
  }}
  .sidebar {{
    position: fixed; top: 0; left: 0; bottom: 0;
    width: 200px; background: {BG_MID};
    border-right: 1px solid {BORDER};
    padding: 24px 0; display: flex; flex-direction: column;
    overflow-y: auto; z-index: 10;
  }}
  .sidebar-title {{
    font-size: 11px; font-weight: 700; color: {TEXT_FAINT};
    letter-spacing: 3px; text-transform: uppercase;
    padding: 0 20px 16px; user-select: none;
  }}
  .nav-item {{
    display: flex; align-items: center; gap: 10px;
    padding: 9px 20px; cursor: pointer;
    color: {TEXT_DIM}; font-size: 13px; font-weight: 500;
    border-left: 3px solid transparent;
    text-decoration: none; transition: all 0.12s;
  }}
  .nav-item:hover {{ color: {TEXT}; background: {BG_HOVER}; }}
  .nav-item.active {{
    color: {ACCENT}; border-left-color: {ACCENT};
    background: rgba(205, 141, 106, 0.06);
  }}
  .nav-icon {{ font-size: 14px; width: 18px; text-align: center; }}
  .sub-nav {{
    border-top: 1px solid {BORDER}; margin-top: 8px; padding-top: 8px;
  }}
  .nav-item.sub {{
    padding-left: 28px; font-size: 12px;
  }}
  .main {{
    margin-left: 200px; flex: 1;
    padding: 32px 48px 48px; max-width: 860px;
  }}
  .page-title {{
    font-size: 22px; font-weight: 700; color: {TEXT};
    margin-bottom: 24px;
  }}
  .section {{ margin-bottom: 28px; }}
  .section-title {{
    font-size: 15px; font-weight: 600; color: {TEXT};
    margin-bottom: 10px;
  }}
  .section-desc {{
    font-size: 12px; color: {TEXT_FAINT}; margin-bottom: 10px;
  }}
  .card {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 12px; padding: 4px 0; overflow: hidden;
  }}
  .card-padded {{ padding: 6px 20px; }}
  .row {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 11px 0; gap: 16px;
  }}
  .row + .row {{ border-top: 1px solid {BORDER}; }}
  .row-label {{ font-size: 13px; color: {TEXT_DIM}; flex-shrink: 0; }}
  .row-hint {{ font-size: 10px; color: {TEXT_FAINT}; margin-top: 2px; }}
  .entry {{
    display: flex; align-items: center; padding: 10px 18px; gap: 12px;
  }}
  .entry + .entry {{ border-top: 1px solid {BORDER}; }}
  .entry-link {{
    flex: 1; min-width: 0; text-decoration: none; transition: opacity 0.15s;
  }}
  .entry-link:hover {{ opacity: 0.8; }}
  .entry-link:hover .entry-title {{ color: {ACCENT}; }}
  .entry-title {{
    font-size: 13px; color: {TEXT}; font-weight: 500;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    transition: color 0.15s;
  }}
  .entry-url {{
    font-size: 10px; color: {TEXT_FAINT}; font-family: monospace;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .entry-date {{ font-size: 10px; color: {TEXT_FAINT}; flex-shrink: 0; }}
  input[type="text"], input[type="number"], select {{
    padding: 8px 12px; font-size: 13px;
    background: {BG_CARD}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    font-family: inherit; flex: 1; min-width: 0;
  }}
  input[type="text"]:focus, input[type="number"]:focus, select:focus {{
    border-color: {ACCENT}; outline: none;
  }}
  input[type="text"]:read-only {{ opacity: 0.5; cursor: not-allowed; }}
  select {{ cursor: pointer; }}
  select option {{ background: {BG_CARD}; color: {TEXT}; }}
  .toggle {{ position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }}
  .toggle input {{ opacity: 0; width: 0; height: 0; }}
  .toggle .slider {{
    position: absolute; cursor: pointer; inset: 0;
    background: {BG_ACTIVE}; border-radius: 22px; transition: 0.2s;
  }}
  .toggle .slider:before {{
    content: ""; position: absolute;
    height: 16px; width: 16px; left: 3px; bottom: 3px;
    background: {TEXT_FAINT}; border-radius: 50%; transition: 0.2s;
  }}
  .toggle input:checked + .slider {{ background: {ACCENT}; }}
  .toggle input:checked + .slider:before {{ transform: translateX(18px); background: {BG_DARK}; }}
  .btn {{
    padding: 9px 24px; font-size: 13px; font-weight: 600;
    border: none; border-radius: 8px; cursor: pointer;
    font-family: inherit; transition: all 0.15s ease;
    text-decoration: none; display: inline-block;
  }}
  .btn-primary {{ background: {ACCENT}; color: {BG_DARK}; }}
  .btn-primary:hover {{ background: {ACCENT_HOVER}; }}
  .btn-secondary {{ background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; }}
  .btn-secondary:hover {{ background: {BG_HOVER}; border-color: {ACCENT}; }}
  .act-btn {{
    padding: 4px 12px; font-size: 11px; font-weight: 500;
    border: 1px solid {BORDER}; border-radius: 5px;
    background: {BG_MID}; color: {TEXT_DIM}; cursor: pointer;
    font-family: inherit; flex-shrink: 0; text-decoration: none;
    display: inline-block;
  }}
  .act-btn:hover {{ background: {ACCENT}; border-color: {ACCENT}; color: {BG_DARK}; }}
  .act-btn.danger {{ border-color: {RED}; color: {RED}; background: transparent; }}
  .act-btn.danger:hover {{ background: {RED}; color: {BG_DARK}; }}
  .act-btn.visit {{ border-color: {GREEN}; color: {GREEN}; background: transparent; }}
  .act-btn.visit:hover {{ background: {GREEN}; color: {BG_DARK}; }}
  .empty {{ text-align: center; padding: 40px 20px; color: {TEXT_FAINT}; font-size: 14px; }}
  .stat-row {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }}
  .stat-card {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 16px; text-align: center;
  }}
  .stat-num {{
    font-size: 28px; font-weight: 700;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    color: {ACCENT};
  }}
  .stat-label {{
    font-size: 10px; color: {TEXT_FAINT};
    text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;
  }}
  .dot {{
    display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; flex-shrink: 0;
  }}
  .dot.red {{ background: {RED}; }}
  .dot.green {{ background: {GREEN}; }}
  .dot.yellow {{ background: {YELLOW}; }}
  .dot.dim {{ background: {TEXT_FAINT}; }}
  .search {{
    width: 100%; padding: 10px 16px; font-size: 14px;
    background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 10px; margin-bottom: 16px; font-family: inherit;
  }}
  .search:focus {{ border-color: {ACCENT}; outline: none; }}
  .toast {{
    position: fixed; bottom: 24px; left: 50%;
    transform: translateX(-50%);
    padding: 10px 24px; border-radius: 8px;
    background: {BG_CARD}; border: 1px solid {GREEN};
    color: {GREEN}; font-size: 13px;
    opacity: 0; transition: opacity 0.3s ease;
    z-index: 100; pointer-events: none;
  }}
  .toast.visible {{ opacity: 1; }}
  .toast.error {{ border-color: {RED}; color: {RED}; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .main > * {{ animation: fadeIn 0.3s ease both; }}
  {extra_css}
</style>
</head>
<body>
  <nav class="sidebar">
    <div class="sidebar-title">{__app_name__}</div>
    {nav_items}
    {sub_nav_html}
  </nav>
  <div class="main">
    <div class="page-title">{title}</div>
    {content}
  </div>
  <div class="toast" id="toast"></div>
  <script>
    function showSection(name, el) {{
      document.querySelectorAll('.panel').forEach(function(p) {{ p.classList.remove('active'); }});
      var panel = document.getElementById('panel-' + name);
      if (panel) panel.classList.add('active');
      document.querySelectorAll('.nav-item.sub').forEach(function(n) {{ n.classList.remove('active'); }});
      if (el) el.classList.add('active');
      history.replaceState(null, '', '#' + name);
    }}
    (function() {{
      var hash = location.hash.replace('#', '');
      if (hash && document.getElementById('panel-' + hash)) {{
        showSection(hash, document.querySelector('.nav-item.sub[href="#' + hash + '"]'));
      }} else {{
        var first = document.querySelector('.panel');
        if (first) first.classList.add('active');
      }}
    }})();
    function showToast(msg, isError) {{
      var t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast visible' + (isError ? ' error' : '');
      setTimeout(function() {{ t.className = 'toast'; }}, 3000);
    }}
    {extra_js}
  </script>
</body>
</html>"""

    # ── Page generators ──────────────────────────────────────────

    def _page_bookmarks(self):
        bookmarks = storage.load_bookmarks()
        rows = ""
        for bm in bookmarks:
            esc_url = html_mod.escape(bm.get("url", ""))
            esc_title = html_mod.escape(bm.get("title", esc_url)[:80])
            rows += (
                f'<div class="entry">'
                f'<a href="{esc_url}" class="entry-link">'
                f'<div class="entry-title">{esc_title}</div>'
                f'<div class="entry-url">{esc_url}</div></a>'
                f'<button class="act-btn danger" '
                f"onclick=\"pageAct('del_bookmark','{esc_url}')\">Delete</button>"
                f'</div>'
            )
        if not bookmarks:
            rows = '<div class="empty">No bookmarks yet. Press Ctrl+D to bookmark a page.</div>'

        content = f"""
    <div class="section-desc">{len(bookmarks)} saved</div>
    <div class="card">{rows}</div>"""

        return self._wrap("Bookmarks", "bookmarks", content, extra_js="""
    function pageAct(action, arg) {
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action:action,arg:arg}));
      setTimeout(function(){ location.reload(); }, 200);
    }""")

    def _page_history(self):
        import time as _time
        history = storage.load_history()
        rows_js = []
        for h in history[:2000]:
            ts = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(h.get("visited", 0)))
            esc_url = html_mod.escape(h.get("url", ""))
            esc_title = html_mod.escape(h.get("title", "")[:80])
            rows_js.append(f'{{"t":"{esc_title}","u":"{esc_url}","d":"{ts}"}}')
        history_json = "[" + ",\n".join(rows_js) + "]"

        content = f"""
    <div class="section-desc">{len(history)} entries</div>
    <input class="search" type="text" placeholder="Filter history..." oninput="filterHistory(this.value)">
    <div style="display:flex;justify-content:flex-end;margin-bottom:12px;">
      <button class="act-btn danger" onclick="if(confirm('Clear all history?'))pageAct('clear_history','')">Clear All History</button>
    </div>
    <div class="card" id="historyList" style="max-height:70vh;overflow-y:auto;"></div>"""

        return self._wrap("History", "history", content, extra_js=f"""
    var _history = {history_json};
    function esc(s) {{ var d = document.createElement('span'); d.textContent = s; return d.innerHTML; }}
    function renderHistory(items) {{
      var el = document.getElementById('historyList');
      if (!items.length) {{ el.innerHTML = '<div class="empty">No matching history.</div>'; return; }}
      var h = '';
      for (var i = 0; i < items.length && i < 500; i++) {{
        var e = items[i];
        h += '<div class="entry"><a class="entry-link" href="' + e.u + '">' +
          '<div class="entry-title">' + esc(e.t || e.u) + '</div>' +
          '<div class="entry-url">' + esc(e.u) + '</div></a>' +
          '<span class="entry-date">' + e.d + '</span></div>';
      }}
      el.innerHTML = h;
    }}
    function filterHistory(q) {{
      if (!q) {{ renderHistory(_history); return; }}
      var lq = q.toLowerCase();
      renderHistory(_history.filter(function(e) {{
        return (e.t && e.t.toLowerCase().indexOf(lq) !== -1) ||
               (e.u && e.u.toLowerCase().indexOf(lq) !== -1);
      }}));
    }}
    function pageAct(action, arg) {{
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({{action:action,arg:arg}}));
      setTimeout(function(){{ location.reload(); }}, 200);
    }}
    renderHistory(_history);""")

    def _page_source(self):
        """Generate the shroud://source page with the stored HTML source."""
        mw = self.parent()
        source = getattr(mw, "_pending_source_html", "") or ""
        source_url = getattr(mw, "_pending_source_url", "") or ""
        esc_source = html_mod.escape(source)
        esc_url = html_mod.escape(source_url)

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Source &mdash; {esc_url or __app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 13px;
  }}
  .toolbar {{
    position: sticky; top: 0; z-index: 10;
    background: {BG_MID}; border-bottom: 1px solid {BORDER};
    padding: 8px 16px; display: flex; align-items: center; gap: 12px;
  }}
  .toolbar-url {{
    font-size: 11px; color: {TEXT_DIM}; flex: 1;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .toolbar-stat {{ font-size: 11px; color: {TEXT_FAINT}; }}
  pre {{
    padding: 16px; margin: 0;
    color: {GREEN}; line-height: 1.5;
    white-space: pre-wrap; word-wrap: break-word;
    counter-reset: line;
  }}
  pre span {{
    display: block;
    counter-increment: line;
  }}
  pre span::before {{
    content: counter(line);
    display: inline-block;
    width: 4em;
    margin-right: 16px;
    text-align: right;
    color: {TEXT_FAINT};
    user-select: none;
  }}
</style>
</head>
<body>
  <div class="toolbar">
    <div class="toolbar-url">{esc_url}</div>
    <div class="toolbar-stat">{len(source)} chars &middot; {source.count(chr(10))+1} lines</div>
  </div>
  <pre id="src"></pre>
  <script>
    var src = {self._json_encode(source)};
    var pre = document.getElementById('src');
    var lines = src.split('\\n');
    for (var i = 0; i < lines.length; i++) {{
      var span = document.createElement('span');
      span.textContent = lines[i];
      pre.appendChild(span);
    }}
  </script>
</body>
</html>"""

    def _page_settings(self):
        """Generate the shroud://settings page."""
        mw = self.parent()
        settings = getattr(mw, "_settings", {})

        # Check DNS registration state
        dns_secret = storage.get_dns_secret(settings)
        is_dns_registered = bool(dns_secret)
        dns_status_color = GREEN if is_dns_registered else TEXT_FAINT
        dns_status_text = "Registered" if is_dns_registered else "Not registered"

        def _chk(key, default=False):
            return "checked" if settings.get(key, default) else ""

        page_links = "\n      ".join(
            f'<a href="shroud://{name}">shroud://{name}</a>'
            for name in _PAGES
        )

        doh_val = settings.get("dns_over_https", "automatic")
        doh_options = "".join(
            f'<option value="{v}"{" selected" if v == doh_val else ""}>{v}</option>'
            for v in ("off", "automatic", "secure")
        )

        dns_disabled = "disabled" if is_dns_registered else ""
        dns_server_readonly = "readonly" if is_dns_registered else ""
        reg_btn_text = "Unregister" if is_dns_registered else "Register"
        reg_btn_action = "unregister" if is_dns_registered else "register"

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Settings &mdash; {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; min-height: 100vh;
  }}

  /* ── Sidebar ── */
  .sidebar {{
    position: fixed; top: 0; left: 0; bottom: 0;
    width: 220px; background: {BG_MID};
    border-right: 1px solid {BORDER};
    padding: 24px 0; display: flex; flex-direction: column;
    overflow-y: auto; z-index: 10;
  }}
  .sidebar-title {{
    font-size: 11px; font-weight: 700; color: {TEXT_FAINT};
    letter-spacing: 3px; text-transform: uppercase;
    padding: 0 20px 20px; user-select: none;
  }}
  .nav-items {{ flex: 1; }}
  .nav-item {{
    display: flex; align-items: center; gap: 10px;
    padding: 10px 20px; cursor: pointer;
    color: {TEXT_DIM}; font-size: 13px; font-weight: 500;
    border-left: 3px solid transparent;
    text-decoration: none; transition: all 0.15s;
  }}
  .nav-item:hover {{ color: {TEXT}; background: {BG_HOVER}; }}
  .nav-item.active {{
    color: {ACCENT}; border-left-color: {ACCENT};
    background: rgba(205, 141, 106, 0.06);
  }}
  .nav-icon {{ font-size: 15px; width: 20px; text-align: center; }}
  .sidebar-footer {{
    padding: 12px 20px; border-top: 1px solid {BORDER};
  }}
  .sidebar-footer a {{
    display: block; padding: 6px 0;
    color: {TEXT_FAINT}; font-size: 12px;
    text-decoration: none;
  }}
  .sidebar-footer a:hover {{ color: {ACCENT}; }}

  /* ── Main content ── */
  .main {{
    margin-left: 220px; flex: 1;
    padding: 32px 48px 80px; max-width: 780px;
  }}
  .page-title {{
    font-size: 22px; font-weight: 700; color: {TEXT};
    margin-bottom: 24px;
  }}

  /* ── Sections ── */
  .section {{ margin-bottom: 32px; }}
  .section-title {{
    font-size: 15px; font-weight: 600; color: {TEXT};
    margin-bottom: 12px;
  }}
  .section-desc {{
    font-size: 12px; color: {TEXT_FAINT}; margin-bottom: 12px;
  }}

  /* ── Rows ── */
  .row {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 11px 0; gap: 16px;
  }}
  .row + .row {{ border-top: 1px solid {BORDER}; }}
  .row-label {{ font-size: 13px; color: {TEXT_DIM}; flex-shrink: 0; }}
  .row-hint {{ font-size: 10px; color: {TEXT_FAINT}; margin-top: 2px; }}

  /* ── Inputs ── */
  input[type="text"], input[type="number"], select {{
    padding: 8px 12px; font-size: 13px;
    background: {BG_CARD}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    font-family: inherit; flex: 1; min-width: 0;
  }}
  input[type="text"]:focus, input[type="number"]:focus, select:focus {{
    border-color: {ACCENT}; outline: none;
  }}
  input[type="text"]:read-only {{ opacity: 0.5; cursor: not-allowed; }}
  select {{ cursor: pointer; }}
  select option {{ background: {BG_CARD}; color: {TEXT}; }}

  /* ── Toggle switch ── */
  .toggle {{ position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }}
  .toggle input {{ opacity: 0; width: 0; height: 0; }}
  .toggle .slider {{
    position: absolute; cursor: pointer; inset: 0;
    background: {BG_ACTIVE}; border-radius: 22px; transition: 0.2s;
  }}
  .toggle .slider:before {{
    content: ""; position: absolute;
    height: 16px; width: 16px; left: 3px; bottom: 3px;
    background: {TEXT_FAINT}; border-radius: 50%; transition: 0.2s;
  }}
  .toggle input:checked + .slider {{ background: {ACCENT}; }}
  .toggle input:checked + .slider:before {{ transform: translateX(18px); background: {BG_DARK}; }}

  /* ── Buttons ── */
  .btn {{
    padding: 9px 24px; font-size: 13px; font-weight: 600;
    border: none; border-radius: 8px; cursor: pointer;
    font-family: inherit; transition: all 0.15s ease;
  }}
  .btn-primary {{ background: {ACCENT}; color: {BG_DARK}; }}
  .btn-primary:hover {{ background: {ACCENT_HOVER}; }}
  .btn-secondary {{ background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; }}
  .btn-secondary:hover {{ background: {BG_HOVER}; border-color: {ACCENT}; }}
  .btn-danger {{ background: transparent; color: {RED}; border: 1px solid {RED}; }}
  .btn-danger:hover {{ background: {RED}; color: {BG_DARK}; }}

  .dns-row {{ display: flex; gap: 8px; align-items: center; flex: 1; min-width: 0; }}
  .dns-status {{ font-size: 12px; }}
  .restart-note {{ font-size: 10px; color: {YELLOW}; margin-top: 2px; }}

  .save-bar {{
    position: fixed; bottom: 0; left: 220px; right: 0;
    padding: 14px 48px;
    background: {BG_MID}; border-top: 1px solid {BORDER};
    display: flex; align-items: center; gap: 12px;
    z-index: 10;
  }}
  .toast {{
    position: fixed; bottom: 70px; left: 50%;
    transform: translateX(-50%);
    padding: 10px 24px; border-radius: 8px;
    background: {BG_CARD}; border: 1px solid {GREEN};
    color: {GREEN}; font-size: 13px;
    opacity: 0; transition: opacity 0.3s ease;
    z-index: 100; pointer-events: none;
  }}
  .toast.visible {{ opacity: 1; }}
  .toast.error {{ border-color: {RED}; color: {RED}; }}

  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .main > * {{ animation: fadeIn 0.3s ease both; }}
</style>
</head>
<body>

  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="sidebar-title">Settings</div>
    <div class="nav-items">
      <a href="#general" class="nav-item active" onclick="showSection('general',this)">
        <span class="nav-icon">\u2699</span> General</a>
      <a href="#search" class="nav-item" onclick="showSection('search',this)">
        <span class="nav-icon">\u2315</span> Search</a>
      <a href="#privacy" class="nav-item" onclick="showSection('privacy',this)">
        <span class="nav-icon">\u26E8</span> Privacy &amp; Security</a>
      <a href="#dns" class="nav-item" onclick="showSection('dns',this)">
        <span class="nav-icon">\u2301</span> DNS</a>
    </div>
    <div class="sidebar-footer">
      <a href="shroud://privacy">Privacy Dashboard</a>
      <a href="shroud://watches">Page Watches</a>
      <a href="shroud://about">About {__app_name__}</a>
      <a href="shroud://shortcuts">Keyboard Shortcuts</a>
    </div>
  </nav>

  <!-- Main content -->
  <div class="main">

    <!-- General -->
    <div class="panel" id="panel-general">
      <div class="page-title">General</div>

      <div class="section">
        <div class="section-title">Startup</div>
        <div class="row">
          <div class="row-label">Restore previous session</div>
          <label class="toggle"><input type="checkbox" id="restore_session"
            {_chk('restore_session', True)}><span class="slider"></span></label>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Browsing</div>
        <div class="row">
          <div class="row-label">JavaScript</div>
          <label class="toggle"><input type="checkbox" id="enable_javascript"
            {_chk('enable_javascript', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Default zoom</div>
          <input type="number" id="default_zoom" min="25" max="500"
            value="{settings.get('default_zoom', 100)}" style="width:90px;flex:none">&nbsp;%
        </div>
        <div class="row">
          <div class="row-label">User agent
            <div class="row-hint">Leave blank for default</div>
          </div>
          <input type="text" id="user_agent"
            value="{html_mod.escape(settings.get('user_agent', ''))}"
            placeholder="Default">
        </div>
        <div class="row">
          <div class="row-label">Remember scroll position
            <div class="row-hint">Resume reading where you left off</div>
          </div>
          <label class="toggle"><input type="checkbox" id="remember_scroll_position"
            {_chk('remember_scroll_position', True)}><span class="slider"></span></label>
        </div>
      </div>
    </div>

    <!-- Search -->
    <div class="panel" id="panel-search" style="display:none">
      <div class="page-title">Search</div>

      <div class="section">
        <div class="section-title">Default Search Engine</div>
        <div class="section-desc">Choose a search engine or enter a custom URL. Use {{}} as placeholder for the query.</div>
        <div class="row">
          <select id="search_preset" onchange="applyPreset(this.value)" style="flex:1">
            <option value="">Custom URL</option>
            <optgroup label="Private">
            <option value="https://duckduckgo.com/?q={{}}">DuckDuckGo \u2014 no tracking, US-based</option>
            <option value="https://www.startpage.com/sp/search?query={{}}">Startpage \u2014 Google results without tracking</option>
            <option value="https://search.brave.com/search?q={{}}">Brave Search \u2014 independent index, no tracking</option>
            <option value="https://www.mojeek.com/search?q={{}}">Mojeek \u2014 own crawler, UK-based, no tracking</option>
            <option value="https://www.qwant.com/?q={{}}">Qwant \u2014 EU-based, GDPR-native privacy</option>
            <option value="https://www.ecosia.org/search?q={{}}">Ecosia \u2014 plants trees, privacy-respecting</option>
            </optgroup>
            <optgroup label="Power User">
            <option value="https://kagi.com/search?q={{}}">Kagi \u2014 paid, no ads, excellent results</option>
            <option value="https://search.marginalia.nu/search?query={{}}">Marginalia \u2014 indie sites, non-commercial web</option>
            <option value="https://wiby.me/?q={{}}">Wiby \u2014 lightweight/personal sites, old-school web</option>
            </optgroup>
            <optgroup label="Standard (trackers blocked by Shroudbyte)">
            <option value="https://www.google.com/search?q={{}}">Google \u2014 best results, tracking blocked by browser</option>
            <option value="https://www.bing.com/search?q={{}}">Bing \u2014 Microsoft search, tracking blocked by browser</option>
            <option value="https://search.yahoo.com/search?p={{}}">Yahoo \u2014 Bing-powered, tracking blocked by browser</option>
            <option value="https://yandex.com/search/?text={{}}">Yandex \u2014 Russian search engine, tracking blocked by browser</option>
            </optgroup>
          </select>
        </div>
        <div class="row">
          <div class="row-label">Search URL</div>
          <input type="text" id="search_engine"
            value="{html_mod.escape(settings.get('search_engine', ''))}"
            placeholder="https://duckduckgo.com/?q={{}}"
            style="font-family:monospace;font-size:12px;">
        </div>
      </div>
    </div>

    <!-- Privacy & Security -->
    <div class="panel" id="panel-privacy" style="display:none">
      <div class="page-title">Privacy &amp; Security</div>

      <div class="section">
        <div class="section-title">Tracking Protection</div>
        <div class="row">
          <div class="row-label">Ad blocker
            <div class="row-hint">Block ads and trackers at the network level</div>
          </div>
          <label class="toggle"><input type="checkbox" id="enable_adblock"
            {_chk('enable_adblock', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Strip tracking parameters
            <div class="row-hint">Remove utm_source, fbclid, gclid, etc. from URLs</div>
          </div>
          <label class="toggle"><input type="checkbox" id="strip_tracking"
            {_chk('strip_tracking', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Do Not Track header
            <div class="row-hint">Send DNT: 1 with every request</div>
          </div>
          <label class="toggle"><input type="checkbox" id="do_not_track"
            {_chk('do_not_track', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Link Intelligence
            <div class="row-hint">Hover links to preview redirect chains and trackers</div>
          </div>
          <label class="toggle"><input type="checkbox" id="link_intelligence"
            {_chk('link_intelligence', True)}><span class="slider"></span></label>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Security</div>
        <div class="row">
          <div class="row-label">HTTPS-only mode
            <div class="row-hint">Automatically upgrade HTTP connections to HTTPS</div>
          </div>
          <label class="toggle"><input type="checkbox" id="https_only"
            {_chk('https_only')}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Fingerprint resistance
            <div class="row-hint">Reduce browser fingerprinting surface</div>
          </div>
          <label class="toggle"><input type="checkbox" id="fingerprint_resistance"
            {_chk('fingerprint_resistance')}><span class="slider"></span></label>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Cookies &amp; Data</div>
        <div class="row">
          <div class="row-label">Auto-delete cookies
            <div class="row-hint">Delete cookies when you close the last tab for a site</div>
          </div>
          <label class="toggle"><input type="checkbox" id="auto_delete_cookies"
            {_chk('auto_delete_cookies')}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Form draft auto-save
            <div class="row-hint">Recover form data after crashes or accidental navigation</div>
          </div>
          <label class="toggle"><input type="checkbox" id="form_draft_autosave"
            {_chk('form_draft_autosave', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Annoyance shield
            <div class="row-hint">Block modals, cookie popups, chat widgets, newsletter overlays</div>
          </div>
          <label class="toggle"><input type="checkbox" id="annoyance_shield"
            {_chk('annoyance_shield', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Screen time tracking
            <div class="row-hint">Track time per domain (opt-in, local only, domain-level)</div>
          </div>
          <label class="toggle"><input type="checkbox" id="screen_time_tracking"
            {_chk('screen_time_tracking')}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Clipboard history
            <div class="row-hint">Track copied text in-memory during the session (never saved to disk)</div>
          </div>
          <label class="toggle"><input type="checkbox" id="clipboard_history"
            {_chk('clipboard_history', True)}><span class="slider"></span></label>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Page Watches</div>
        <div class="row">
          <div class="row-label">Default check interval
            <div class="row-hint">How often to check watched pages for changes</div>
          </div>
          <input type="number" id="page_watch_interval" min="1" max="1440"
            value="{settings.get('page_watch_interval', 3600) // 60}"
            style="width:80px;flex:none">&nbsp;min
        </div>
      </div>
    </div>

    <!-- DNS -->
    <div class="panel" id="panel-dns" style="display:none">
      <div class="page-title">DNS</div>

      <div class="section">
        <div class="section-title">DNS-over-HTTPS</div>
        <div class="section-desc">Encrypt DNS queries. Changes require a browser restart.</div>
        <div class="row">
          <div class="row-label">Mode</div>
          <select id="dns_over_https" {dns_disabled}>{doh_options}</select>
        </div>
        <div class="row">
          <div class="row-label">Provider URL</div>
          <input type="text" id="dns_over_https_provider" {dns_disabled}
            value="{html_mod.escape(settings.get('dns_over_https_provider', ''))}"
            placeholder="https://dns.cloudflare.com/dns-query">
        </div>
      </div>

      <div class="section">
        <div class="section-title">Shroud DNS</div>
        <div class="section-desc">Connect to your own Shroud DNS server for authenticated DNS resolution. Overrides DNS-over-HTTPS when registered.</div>
        <div class="row">
          <div class="row-label">Server</div>
          <div class="dns-row">
            <input type="text" id="custom_dns_server" {dns_server_readonly}
              value="{html_mod.escape(settings.get('custom_dns_server', ''))}"
              placeholder="https://pfsense.local:8853">
            <button class="btn btn-secondary" style="padding:8px 16px;flex:none"
              onclick="settingsAct('{reg_btn_action}')">{reg_btn_text}</button>
          </div>
        </div>
        <div class="row">
          <div class="row-label">Status</div>
          <span class="dns-status" style="color:{dns_status_color}">{dns_status_text}</span>
        </div>
        <div class="row">
          <div class="row-label">Fallback to system DNS
            <div class="row-hint">Use system resolver if Shroud DNS server is unreachable</div>
          </div>
          <label class="toggle"><input type="checkbox" id="custom_dns_fallback"
            {_chk('custom_dns_fallback', True)}><span class="slider"></span></label>
        </div>
      </div>
    </div>

  </div><!-- .main -->

  <!-- Save bar -->
  <div class="save-bar">
    <button class="btn btn-primary" onclick="saveSettings()">Save Settings</button>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    // ── Sidebar navigation ──
    function showSection(name, el) {{
      document.querySelectorAll('.panel').forEach(function(p) {{ p.style.display = 'none'; }});
      document.getElementById('panel-' + name).style.display = '';
      document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
      if (el) el.classList.add('active');
      // Update URL hash without scrolling
      history.replaceState(null, '', '#' + name);
    }}
    // Restore section from hash on load
    (function() {{
      var hash = location.hash.replace('#', '');
      if (hash && document.getElementById('panel-' + hash)) {{
        showSection(hash, document.querySelector('.nav-item[href="#' + hash + '"]'));
      }}
    }})();

    // ── Search preset ──
    function applyPreset(url) {{
      if (url) document.getElementById('search_engine').value = url;
    }}
    (function() {{
      var cur = document.getElementById('search_engine').value;
      var sel = document.getElementById('search_preset');
      for (var i = 0; i < sel.options.length; i++) {{
        if (sel.options[i].value && cur.indexOf(sel.options[i].value.split('?')[0]) !== -1) {{
          sel.selectedIndex = i; break;
        }}
      }}
    }})();

    // ── Settings I/O ──
    function getVal(id) {{
      var el = document.getElementById(id);
      if (!el) return null;
      if (el.type === 'checkbox') return el.checked;
      if (el.type === 'number') return parseInt(el.value, 10);
      return el.value;
    }}

    function saveSettings() {{
      var s = {{
        search_engine: getVal('search_engine'),
        enable_javascript: getVal('enable_javascript'),
        enable_adblock: getVal('enable_adblock'),
        default_zoom: getVal('default_zoom'),
        user_agent: getVal('user_agent'),
        https_only: getVal('https_only'),
        do_not_track: getVal('do_not_track'),
        restore_session: getVal('restore_session'),
        strip_tracking: getVal('strip_tracking'),
        fingerprint_resistance: getVal('fingerprint_resistance'),
        link_intelligence: getVal('link_intelligence'),
        page_watch_interval: getVal('page_watch_interval') * 60,
        auto_delete_cookies: getVal('auto_delete_cookies'),
        form_draft_autosave: getVal('form_draft_autosave'),
        annoyance_shield: getVal('annoyance_shield'),
        screen_time_tracking: getVal('screen_time_tracking'),
        clipboard_history: getVal('clipboard_history'),
        remember_scroll_position: getVal('remember_scroll_position'),
        dns_over_https: getVal('dns_over_https'),
        dns_over_https_provider: getVal('dns_over_https_provider'),
        custom_dns_fallback: getVal('custom_dns_fallback')
      }};
      console.log('__SHROUD_SETTINGS__:' + JSON.stringify({{
        action: 'save', settings: s
      }}));
      showToast('Settings saved');
    }}

    function settingsAct(action) {{
      if (action === 'unregister') {{
        if (!confirm('Unregistering will clear your DNS credentials and restart the browser. Continue?'))
          return;
      }}
      var server = getVal('custom_dns_server') || '';
      console.log('__SHROUD_SETTINGS__:' + JSON.stringify({{
        action: action, server_url: server
      }}));
    }}

    function showToast(msg, isError) {{
      var t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast visible' + (isError ? ' error' : '');
      setTimeout(function() {{ t.className = 'toast'; }}, 3000);
    }}

    window.__shroudSettingsResult = function(data) {{
      if (data.error) showToast(data.error, true);
      else if (data.msg) showToast(data.msg);
      if (data.reload) setTimeout(function() {{ location.reload(); }}, 500);
    }};
  </script>
</body>
</html>"""

    def _page_screentime(self):
        """Generate the shroud://screentime dashboard."""
        import time as _time
        from datetime import datetime, timedelta

        # Flush pending data so the page shows the latest
        mw = self.parent()
        if hasattr(mw, "_screen_time"):
            mw._screen_time._flush()

        data = storage.load_screen_time()
        today = _time.strftime("%Y-%m-%d")

        # Compute date strings for last 7 days
        dates_7d = []
        for i in range(7):
            d = datetime.now() - timedelta(days=i)
            dates_7d.append(d.strftime("%Y-%m-%d"))

        def _fmt(secs):
            if secs < 60:
                return f"{secs}s"
            if secs < 3600:
                return f"{secs // 60}m {secs % 60}s"
            h = secs // 3600
            m = (secs % 3600) // 60
            return f"{h}h {m}m"

        # Today's data — sorted by time
        today_domains = []
        for domain, days in data.items():
            t = days.get(today, 0)
            if t > 0:
                today_domains.append((domain, t))
        today_domains.sort(key=lambda x: -x[1])
        today_total = sum(t for _, t in today_domains)

        # 7-day data
        week_domains: dict[str, int] = {}
        for domain, days in data.items():
            total = sum(days.get(d, 0) for d in dates_7d)
            if total > 0:
                week_domains[domain] = total
        week_sorted = sorted(week_domains.items(), key=lambda x: -x[1])
        week_total = sum(t for _, t in week_sorted)

        # Build today rows
        if today_domains:
            max_today = today_domains[0][1] if today_domains else 1
            today_rows = ""
            for domain, secs in today_domains[:30]:
                pct = min(100, int(secs / max(max_today, 1) * 100))
                esc_d = html_mod.escape(domain)
                today_rows += (
                    f'<div class="time-row">'
                    f'<span class="time-domain">{esc_d}</span>'
                    f'<div class="time-bar-bg"><div class="time-bar" style="width:{pct}%"></div></div>'
                    f'<span class="time-val">{_fmt(secs)}</span>'
                    f'</div>'
                )
        else:
            today_rows = '<div class="empty">No browsing data for today.</div>'

        # Build week rows
        if week_sorted:
            max_week = week_sorted[0][1] if week_sorted else 1
            week_rows = ""
            for domain, secs in week_sorted[:30]:
                pct = min(100, int(secs / max(max_week, 1) * 100))
                esc_d = html_mod.escape(domain)
                week_rows += (
                    f'<div class="time-row">'
                    f'<span class="time-domain">{esc_d}</span>'
                    f'<div class="time-bar-bg"><div class="time-bar" style="width:{pct}%"></div></div>'
                    f'<span class="time-val">{_fmt(secs)}</span>'
                    f'</div>'
                )
        else:
            week_rows = '<div class="empty">No browsing data for the past 7 days.</div>'

        enabled = self.parent()._settings.get("screen_time_tracking", False)
        status = (
            f'<div class="section-desc" style="color:{GREEN}">Tracking is enabled.</div>'
            if enabled else
            f'<div class="section-desc" style="color:{TEXT_FAINT}">'
            f'Tracking is disabled. Enable it in <a href="shroud://settings#privacy" '
            f'style="color:{ACCENT}">Settings</a>.</div>'
        )

        extra_css = f"""
  .time-row {{
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0;
  }}
  .time-row + .time-row {{ border-top: 1px solid {BORDER}; }}
  .time-domain {{
    font-size: 13px; color: {TEXT}; min-width: 160px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .time-bar-bg {{
    flex: 1; height: 6px; background: {BG_ACTIVE};
    border-radius: 3px; overflow: hidden;
  }}
  .time-bar {{
    height: 100%; background: {ACCENT};
    border-radius: 3px; transition: width 0.3s ease;
  }}
  .time-val {{
    font-size: 12px; color: {TEXT_DIM}; min-width: 70px; text-align: right;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
  }}"""

        content = f"""
    {status}
    <div class="stat-row" style="grid-template-columns:repeat(2,1fr)">
      <div class="stat-card">
        <div class="stat-num">{_fmt(today_total)}</div>
        <div class="stat-label">Today</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{_fmt(week_total)}</div>
        <div class="stat-label">Past 7 Days</div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Today</div>
      <div class="card card-padded">
        {today_rows}
      </div>
    </div>

    <div class="section">
      <div class="section-title">Past 7 Days</div>
      <div class="card card-padded">
        {week_rows}
      </div>
    </div>

    <div style="display:flex;justify-content:flex-end;margin-top:8px;">
      <button class="act-btn danger" onclick="if(confirm('Clear all screen time data?')){{
        console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({{action:'clear_screentime',arg:''}}));
        setTimeout(function(){{ location.reload(); }}, 200);
      }}">Clear All Data</button>
    </div>"""

        return self._wrap("Screen Time", "screentime", content, extra_css=extra_css)

    def _page_watches(self):
        """Generate the shroud://watches page watch management page."""
        import time as _time

        watches = storage.load_watches()
        active = sum(1 for w in watches if w.get("enabled", True))
        total_changes = sum(w.get("change_count", 0) for w in watches)

        def _ago(ts):
            if not ts:
                return "never"
            d = _time.time() - ts
            if d < 60:
                return "just now"
            if d < 3600:
                return f"{int(d / 60)}m ago"
            if d < 86400:
                return f"{int(d / 3600)}h ago"
            return f"{int(d / 86400)}d ago"

        def _interval_label(s):
            if s < 60:
                return f"{s}s"
            if s < 3600:
                return f"{s // 60}m"
            return f"{s // 3600}h"

        # ── build watch cards ──
        cards = ""
        for w in watches:
            url = w.get("url", "")
            title = w.get("title", url)
            esc_url = html_mod.escape(url)
            esc_title = html_mod.escape(title[:80])
            enabled = w.get("enabled", True)
            interval = w.get("interval", 3600)
            last_check = _ago(w.get("last_check", 0))
            last_changed = _ago(w.get("last_changed", 0))
            changes = w.get("change_count", 0)

            status_dot = "green" if enabled else "dim"
            toggle_label = "Pause" if enabled else "Resume"

            # Interval selector
            intervals = [300, 900, 1800, 3600, 7200, 14400, 43200, 86400]
            options = "".join(
                f'<option value="{v}"'
                f'{" selected" if v == interval else ""}>'
                f'{_interval_label(v)}</option>'
                for v in intervals
            )
            interval_sel = (
                f'<select class="interval-sel" '
                f"onchange=\"watchAct('set_interval','{esc_url}',this.value)\">"
                f'{options}</select>'
            )

            # Diff section
            diff_html = ""
            last_diff = w.get("last_diff", "")
            if last_diff:
                diff_lines = ""
                for line in last_diff.split("\n")[:60]:
                    esc_line = html_mod.escape(line)
                    if line.startswith("+") and not line.startswith("+++"):
                        diff_lines += f'<div class="diff-add">{esc_line}</div>'
                    elif line.startswith("-") and not line.startswith("---"):
                        diff_lines += f'<div class="diff-del">{esc_line}</div>'
                    elif line.startswith("@@"):
                        diff_lines += f'<div class="diff-hunk">{esc_line}</div>'
                    else:
                        diff_lines += f'<div class="diff-ctx">{esc_line}</div>'
                diff_html = (
                    f'<details class="diff-box"><summary>View last diff</summary>'
                    f'<div class="diff-content">{diff_lines}</div></details>'
                )

            cards += f"""
    <div class="watch-card">
      <div class="watch-header">
        <span class="dot {status_dot}"></span>
        <span class="watch-title">{esc_title}</span>
      </div>
      <div class="watch-url">{esc_url}</div>
      <div class="watch-meta">
        Checked {last_check} &middot;
        Changed {last_changed} &middot;
        {changes} change{"s" if changes != 1 else ""} &middot;
        Every {interval_sel}
      </div>
      <div class="watch-actions">
        <button class="act-btn" onclick="watchAct('check_now','{esc_url}')">Check Now</button>
        <button class="act-btn" onclick="watchAct('toggle','{esc_url}')">{toggle_label}</button>
        <button class="act-btn danger" onclick="watchAct('remove','{esc_url}')">Remove</button>
        <a class="act-btn visit" href="{esc_url}" target="_blank">Visit</a>
      </div>
      {diff_html}
    </div>"""

        if not watches:
            cards = (
                '<div class="empty">No pages watched yet. '
                'Right-click any page and choose "Watch This Page".</div>'
            )

        content = f"""
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-num">{len(watches)}</div>
        <div class="stat-label">Total</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{active}</div>
        <div class="stat-label">Active</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{total_changes}</div>
        <div class="stat-label">Changes</div>
      </div>
    </div>

    {cards}"""

        extra_css = f"""
  .watch-card {{
    width: 100%; background: {BG_CARD};
    border: 1px solid {BORDER}; border-radius: 12px;
    padding: 16px 20px; margin-bottom: 10px;
  }}
  .watch-header {{
    display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
  }}
  .watch-title {{ font-size: 14px; font-weight: 600; color: {TEXT}; }}
  .watch-url {{
    font-size: 11px; color: {TEXT_FAINT}; word-break: break-all;
    font-family: monospace; margin-bottom: 8px;
  }}
  .watch-meta {{
    font-size: 11px; color: {TEXT_DIM}; margin-bottom: 10px;
    display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  }}
  .watch-actions {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .interval-sel {{
    padding: 2px 6px; font-size: 11px;
    background: {BG_DARK}; color: {TEXT_DIM};
    border: 1px solid {BORDER}; border-radius: 4px;
    font-family: inherit; cursor: pointer;
  }}
  .diff-box {{
    margin-top: 10px; border-top: 1px solid {BORDER}; padding-top: 8px;
  }}
  .diff-box summary {{
    font-size: 11px; color: {ACCENT}; cursor: pointer;
    user-select: none;
  }}
  .diff-content {{
    margin-top: 8px; padding: 10px;
    background: {BG_DARK}; border-radius: 8px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px; overflow-x: auto; max-height: 300px; overflow-y: auto;
  }}
  .diff-add {{ color: {GREEN}; }}
  .diff-del {{ color: {RED}; }}
  .diff-hunk {{ color: {YELLOW}; }}
  .diff-ctx {{ color: {TEXT_FAINT}; }}"""

        extra_js = """
    function watchAct(action, url, extra) {
      console.log('__SHROUD_WATCH__:' + JSON.stringify({
        action: action, url: url || '', interval: extra || ''
      }));
      setTimeout(function() { location.reload(); }, 300);
    }"""

        return self._wrap("Page Watches", "watches", content,
                          extra_css=extra_css, extra_js=extra_js)

    def _page_privacy(self):
        """Generate the shroud://privacy global privacy dashboard."""
        mw = self.parent()
        adblocker = getattr(mw, "_adblocker", None)
        all_cookies = getattr(mw, "_all_cookies", [])

        # ── aggregate data ──
        total_blocked = 0
        total_third_party = 0
        total_stripped = set()
        site_rows = []

        site_exc = storage.load_site_exceptions()

        if adblocker:
            for site_host, tracker in sorted(adblocker._page_data.items()):
                blocked_count = sum(tracker.blocked.values())
                tp_count = sum(tracker.third_party.values())
                total_blocked += blocked_count
                total_third_party += tp_count
                total_stripped |= tracker.stripped_params

                this_exc = site_exc.get(site_host, {})

                blocked_items = ""
                for h, c in sorted(tracker.blocked.items(), key=lambda x: -x[1]):
                    esc_site = html_mod.escape(site_host)
                    esc_h = html_mod.escape(h)
                    exc_val = this_exc.get(h)
                    if exc_val:
                        btn = (f'<button class="act-btn" onclick='
                               f"\"privacyAct('undo_exc','{esc_site}','{esc_h}')\""
                               f'>Undo ({exc_val})</button>')
                    else:
                        btn = (f'<button class="act-btn" onclick='
                               f"\"privacyAct('allow','{esc_site}','{esc_h}')\""
                               f'>Allow</button>')
                    blocked_items += (
                        f'<tr><td class="dot-cell"><span class="dot red"></span></td>'
                        f'<td class="domain">{esc_h}</td>'
                        f'<td class="count">{c}</td>'
                        f'<td class="act-cell">{btn}</td></tr>'
                    )

                tp_items = ""
                for h, c in sorted(tracker.third_party.items(), key=lambda x: -x[1]):
                    esc_site = html_mod.escape(site_host)
                    esc_h = html_mod.escape(h)
                    exc_val = this_exc.get(h)
                    if exc_val:
                        btn = (f'<button class="act-btn" onclick='
                               f"\"privacyAct('undo_exc','{esc_site}','{esc_h}')\""
                               f'>Undo ({exc_val})</button>')
                    else:
                        btn = (f'<button class="act-btn" onclick='
                               f"\"privacyAct('block','{esc_site}','{esc_h}')\""
                               f'>Block</button>')
                    tp_items += (
                        f'<tr><td class="dot-cell"><span class="dot green"></span></td>'
                        f'<td class="domain">{esc_h}</td>'
                        f'<td class="count">{c}</td>'
                        f'<td class="act-cell">{btn}</td></tr>'
                    )

                params_html = ""
                if tracker.stripped_params:
                    tags = " ".join(
                        f'<span class="param-tag">{html_mod.escape(p)}</span>'
                        for p in sorted(tracker.stripped_params)
                    )
                    params_html = f'<div class="params-row">{tags}</div>'

                site_rows.append(f"""
        <div class="site-card">
          <div class="site-header">
            <span class="site-name">{html_mod.escape(site_host)}</span>
            <span class="site-stats">{blocked_count} blocked &middot; {tp_count} third-party</span>
          </div>
          <table class="req-table">{blocked_items}{tp_items}</table>
          {params_html}
        </div>""")

        sites_html = "\n".join(site_rows) if site_rows else (
            '<div class="empty">No browsing data collected yet. '
            'Visit some sites and come back.</div>'
        )

        # ── cookies ──
        cookies_by_domain: dict[str, int] = {}
        for cookie in all_cookies:
            d = cookie.domain().lstrip(".")
            cookies_by_domain[d] = cookies_by_domain.get(d, 0) + 1

        total_cookies = sum(cookies_by_domain.values())
        cookie_rows = ""
        for d, c in sorted(cookies_by_domain.items(), key=lambda x: -x[1])[:30]:
            esc_d = html_mod.escape(d)
            cookie_rows += (
                f'<tr><td class="domain">{esc_d}</td>'
                f'<td class="count">{c}</td>'
                f'<td class="act-cell">'
                f'<button class="act-btn danger" onclick='
                f"\"privacyAct('del_cookies','{esc_d}')\">"
                f'Delete</button></td></tr>'
            )
        if not cookie_rows:
            cookie_rows = '<tr><td class="domain" colspan="3">No cookies stored</td></tr>'

        # ── permissions ──
        all_perms = storage.load_permissions()
        perm_rows = ""
        for host, features in sorted(all_perms.items()):
            for feat, decision in sorted(features.items()):
                color = "green" if decision == "allow" else "red"
                esc_host = html_mod.escape(host)
                esc_feat = html_mod.escape(feat)
                perm_rows += (
                    f'<tr><td class="dot-cell"><span class="dot {color}"></span></td>'
                    f'<td class="domain">{esc_host}</td>'
                    f'<td class="perm-feat">{esc_feat}</td>'
                    f'<td class="perm-dec">{html_mod.escape(decision)}</td>'
                    f'<td class="act-cell">'
                    f'<button class="act-btn danger" onclick='
                    f"\"privacyAct('revoke','{esc_host}','{esc_feat}')\">"
                    f'Revoke</button></td></tr>'
                )
        if not perm_rows:
            perm_rows = '<tr><td class="domain" colspan="5">No permissions set</td></tr>'

        # ── site exceptions ──
        exc_rows = ""
        for site_h, overrides in sorted(site_exc.items()):
            for tracker_h, action in sorted(overrides.items()):
                color = "green" if action == "allow" else "red"
                esc_s = html_mod.escape(site_h)
                esc_t = html_mod.escape(tracker_h)
                exc_rows += (
                    f'<tr><td class="dot-cell"><span class="dot {color}"></span></td>'
                    f'<td class="domain">{esc_s}</td>'
                    f'<td class="perm-feat">{esc_t}</td>'
                    f'<td class="perm-dec">{html_mod.escape(action)}</td>'
                    f'<td class="act-cell">'
                    f'<button class="act-btn danger" onclick='
                    f"\"privacyAct('undo_exc','{esc_s}','{esc_t}')\">"
                    f'Remove</button></td></tr>'
                )

        exc_section = ""
        if exc_rows:
            exc_section = f"""
    <div class="section">
      <h2>Site Exceptions</h2>
      <div class="info-card"><table class="req-table">{exc_rows}</table></div>
    </div>"""

        content = f"""
    <div class="stat-row" style="grid-template-columns: repeat(4, 1fr);">
      <div class="stat-card">
        <div class="stat-num blocked">{total_blocked}</div>
        <div class="stat-label">Blocked</div>
      </div>
      <div class="stat-card">
        <div class="stat-num third-party">{total_third_party}</div>
        <div class="stat-label">Third-Party</div>
      </div>
      <div class="stat-card">
        <div class="stat-num stripped">{len(total_stripped)}</div>
        <div class="stat-label">Params Stripped</div>
      </div>
      <div class="stat-card">
        <div class="stat-num cookies">{total_cookies}</div>
        <div class="stat-label">Cookies</div>
      </div>
    </div>

    <div class="section">
      <h2>Sites Visited</h2>
      {sites_html}
    </div>

    <div class="section">
      <h2>Cookies ({total_cookies})</h2>
      <div class="info-card">
        <table class="req-table">{cookie_rows}</table>
      </div>
    </div>

    <div class="section">
      <h2>Permissions</h2>
      <div class="info-card">
        <table class="req-table">{perm_rows}</table>
      </div>
    </div>

    {exc_section}

    <div class="reload-banner" id="reloadBanner">
      Changes saved. Reload affected tabs for them to take effect.
      <button onclick="location.reload()">Refresh dashboard</button>
    </div>"""

        extra_css = f"""
  .stat-num.blocked {{ color: {RED}; }}
  .stat-num.third-party {{ color: {YELLOW}; }}
  .stat-num.stripped {{ color: {ACCENT}; }}
  .stat-num.cookies {{ color: {GREEN}; }}
  .section h2 {{
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 3px; color: {TEXT_FAINT};
    font-weight: 600; margin-bottom: 10px; padding-left: 4px;
  }}
  .info-card {{
    width: 100%; background: {BG_CARD};
    border: 1px solid {BORDER}; border-radius: 12px;
    padding: 8px 16px; overflow: hidden;
  }}
  .site-card {{
    width: 100%; background: {BG_CARD};
    border: 1px solid {BORDER}; border-radius: 12px;
    padding: 14px 18px; margin-bottom: 10px;
  }}
  .site-header {{
    display: flex; justify-content: space-between;
    align-items: center; margin-bottom: 8px;
  }}
  .site-name {{
    font-size: 14px; font-weight: 600; color: {TEXT};
  }}
  .site-stats {{
    font-size: 11px; color: {TEXT_FAINT};
  }}
  .req-table {{ width: 100%; border-collapse: collapse; }}
  .req-table td {{ padding: 5px 0; font-size: 12px; }}
  .req-table td.dot-cell {{ width: 18px; }}
  .req-table td.domain {{ color: {TEXT_DIM}; }}
  .req-table td.count {{
    text-align: right; color: {TEXT_FAINT};
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px;
  }}
  .req-table td.perm-feat {{
    color: {TEXT_DIM}; font-family: monospace; font-size: 11px;
  }}
  .req-table td.perm-dec {{
    text-align: right; font-size: 11px;
  }}
  .req-table tr + tr td {{ border-top: 1px solid {BORDER}; }}
  .params-row {{
    margin-top: 8px; padding-top: 8px;
    border-top: 1px solid {BORDER};
    display: flex; gap: 6px; flex-wrap: wrap;
  }}
  .param-tag {{
    display: inline-block;
    padding: 2px 8px; border-radius: 4px;
    font-size: 10px; font-family: monospace;
    background: rgba(212, 168, 87, 0.12);
    color: {YELLOW};
    border: 1px solid rgba(212, 168, 87, 0.2);
  }}
  .act-cell {{ text-align: right; width: 80px; }}
  .reload-banner {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: {BG_CARD}; border-top: 1px solid {ACCENT};
    padding: 10px 24px; text-align: center;
    font-size: 13px; color: {ACCENT_TEXT}; z-index: 100;
    display: none;
  }}
  .reload-banner button {{
    margin-left: 12px; padding: 5px 16px; font-size: 12px;
    border: none; border-radius: 6px;
    background: {ACCENT}; color: {BG_DARK};
    cursor: pointer; font-weight: 600; font-family: inherit;
  }}
  .reload-banner button:hover {{ background: {ACCENT_HOVER}; }}"""

        extra_js = """
    function privacyAct(action, arg1, arg2) {
      console.log('__SHROUD_PRIVACY__:' + JSON.stringify({
        action: action, arg1: arg1 || '', arg2: arg2 || ''
      }));
      // Show reload banner and refresh page after Python processes
      document.getElementById('reloadBanner').style.display = 'block';
      setTimeout(function() { location.reload(); }, 200);
    }"""

        return self._wrap("Privacy Dashboard", "privacy", content,
                          extra_css=extra_css, extra_js=extra_js)

    def _page_about(self):
        from PyQt6.QtCore import PYQT_VERSION_STR, qVersion

        py_ver = (
            f"{sys.version_info.major}.{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        )
        qt_ver = qVersion()
        pyqt_ver = PYQT_VERSION_STR

        ua = self._profile.httpUserAgent()
        m = re.search(r"Chrome/([\d.]+)", ua)
        chromium_ver = m.group(1) if m else "Unknown"

        try:
            import cryptography
            crypto_ver = cryptography.__version__
        except Exception:
            crypto_ver = "N/A"

        try:
            import keyring
            from importlib.metadata import version as _pkg_ver
            kr_ver_str = _pkg_ver("keyring")
            kr_backend = type(keyring.get_keyring()).__qualname__
            kr_ver = f"{kr_ver_str} ({kr_backend})"
        except Exception:
            kr_ver = "Not available"

        os_info = f"{platform.system()} {platform.release()}"
        arch = platform.machine()
        profile_path = str(storage.DATA_DIR)

        rows = [
            ("Python", py_ver),
            ("Qt", qt_ver),
            ("PyQt6", pyqt_ver),
            ("Chromium", chromium_ver),
            ("cryptography", crypto_ver),
            ("keyring", kr_ver),
            ("Platform", f"{os_info} ({arch})"),
            ("Profile", profile_path),
        ]
        table_rows = "\n".join(
            f'            <tr><td class="label">{label}</td>'
            f'<td class="value">{html_mod.escape(value)}</td></tr>'
            for label, value in rows
        )

        page_links = "\n      ".join(
            f'<a href="shroud://{name}">shroud://{name}</a>'
            for name in _PAGES
        )

        content = f"""
    <div class="section-desc">Version {__version__}</div>
    <div class="info-card">
      <table>
{table_rows}
      </table>
    </div>
    <div class="section-label">Internal Pages</div>
    <div class="pages">
      {page_links}
    </div>"""

        extra_css = f"""
  .info-card {{
    width: 100%; background: {BG_CARD};
    border: 1px solid {BORDER}; border-radius: 12px;
    padding: 20px 24px; margin-bottom: 36px;
  }}
  .info-card table {{ width: 100%; border-collapse: collapse; }}
  .info-card td {{ padding: 9px 0; font-size: 13px; vertical-align: top; }}
  .info-card td.label {{ color: {TEXT_FAINT}; width: 100px; font-weight: 500; }}
  .info-card td.value {{
    color: {TEXT};
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 12px; word-break: break-all;
  }}
  .info-card tr + tr td {{ border-top: 1px solid {BORDER}; }}
  .section-label {{
    font-size: 10px; text-transform: uppercase;
    letter-spacing: 3px; color: {TEXT_FAINT};
    margin-bottom: 14px; font-weight: 600;
  }}
  .pages {{ display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }}
  .pages a {{
    padding: 8px 16px;
    background: rgba(28, 27, 36, 0.6);
    border: 1px solid rgba(40, 38, 51, 0.5);
    border-radius: 8px; text-decoration: none;
    color: {ACCENT}; font-size: 13px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    transition: all 0.2s ease;
  }}
  .pages a:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
    transform: translateY(-1px);
  }}"""

        return self._wrap("About Shroudbyte", "about", content,
                          extra_css=extra_css)

    def _page_shortcuts(self):
        categories = [
            ("Tabs", [
                ("Ctrl+T", "New Tab"),
                ("Ctrl+W", "Close Tab"),
                ("Ctrl+Shift+T", "Reopen Closed Tab"),
                ("Ctrl+N", "New Window"),
                ("Ctrl+Shift+P", "New Private Window"),
                ("Alt+1\u20139", "Switch to Tab 1\u20139"),
            ]),
            ("Navigation", [
                ("Ctrl+L / F6", "Focus URL Bar"),
                ("F5 / Ctrl+R", "Reload"),
                ("Ctrl+Shift+R", "Hard Reload"),
                ("Escape", "Stop Loading"),
                ("Ctrl+F", "Find on Page"),
            ]),
            ("View", [
                ("Ctrl+=", "Zoom In"),
                ("Ctrl+\u2212", "Zoom Out"),
                ("Ctrl+0", "Reset Zoom"),
                ("F9", "Reader Mode"),
                ("F11", "Full Screen"),
                ("Ctrl+U", "View Source"),
                ("Ctrl+P", "Print"),
                ("Ctrl+Shift+S", "Save as PDF"),
                ("Ctrl+Shift+E", "Screenshot"),
            ]),
            ("Tools", [
                ("Ctrl+D", "Bookmark Page"),
                ("Ctrl+Shift+B", "Show Bookmarks"),
                ("Ctrl+H", "Show History"),
                ("Ctrl+Shift+M", "Password Manager"),
                ("Ctrl+Shift+L", "Auto-fill Password"),
                ("Ctrl+J", "Downloads"),
                ("F12", "Developer Tools"),
                ("F1", "Keyboard Shortcuts"),
                ("Ctrl+Q", "Quit"),
            ]),
        ]

        sections_html = ""
        for cat_name, shortcuts in categories:
            rows = "\n".join(
                f'              <tr>'
                f'<td class="key"><kbd>{html_mod.escape(key)}</kbd></td>'
                f'<td class="desc">{html_mod.escape(desc)}</td>'
                f'</tr>'
                for key, desc in shortcuts
            )
            sections_html += f"""
    <div class="category">
      <h2>{html_mod.escape(cat_name)}</h2>
      <div class="info-card">
        <table>
{rows}
        </table>
      </div>
    </div>"""

        content = sections_html

        extra_css = f"""
  .category {{ width: 100%; margin-bottom: 28px; }}
  .category h2 {{
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 3px; color: {TEXT_FAINT};
    font-weight: 600; margin-bottom: 10px; padding-left: 4px;
  }}
  .info-card {{
    width: 100%; background: {BG_CARD};
    border: 1px solid {BORDER}; border-radius: 12px;
    padding: 8px 20px;
  }}
  .info-card table {{ width: 100%; border-collapse: collapse; }}
  .info-card td {{ padding: 10px 0; font-size: 13px; vertical-align: middle; }}
  .info-card td.key {{ width: 180px; }}
  .info-card td.desc {{ color: {TEXT_DIM}; }}
  .info-card tr + tr td {{ border-top: 1px solid {BORDER}; }}
  kbd {{
    display: inline-block;
    padding: 4px 10px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 12px;
    color: {TEXT};
    background: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    line-height: 1;
  }}"""

        return self._wrap("Keyboard Shortcuts", "shortcuts", content,
                          extra_css=extra_css)

    def _page_error(self, url_str):
        safe_url = html_mod.escape(url_str)
        page_links = "\n      ".join(
            f'<a href="shroud://{name}">shroud://{name}</a>'
            for name in _PAGES
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Page Not Found</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    min-height: 100vh;
  }}
  .content {{ text-align: center; max-width: 480px; padding: 0 24px; }}
  .error-code {{
    font-size: 72px; font-weight: 700; color: {BORDER};
    margin-bottom: 8px;
  }}
  .title {{ font-size: 20px; font-weight: 600; margin-bottom: 12px; }}
  .message {{
    font-size: 14px; color: {TEXT_FAINT};
    margin-bottom: 36px; line-height: 1.6;
  }}
  .message code {{
    color: {ACCENT}; background: {BG_CARD};
    padding: 2px 8px; border-radius: 4px; font-size: 13px;
  }}
  .section-label {{
    font-size: 10px; text-transform: uppercase;
    letter-spacing: 3px; color: {TEXT_FAINT};
    margin-bottom: 14px; font-weight: 600;
  }}
  .pages {{ display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }}
  .pages a {{
    padding: 8px 16px;
    background: rgba(28, 27, 36, 0.6);
    border: 1px solid rgba(40, 38, 51, 0.5);
    border-radius: 8px; text-decoration: none;
    color: {ACCENT}; font-size: 13px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    transition: all 0.2s ease;
  }}
  .pages a:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .error-code    {{ animation: fadeIn 0.4s ease 0.04s both; }}
  .title         {{ animation: fadeIn 0.4s ease 0.10s both; }}
  .message       {{ animation: fadeIn 0.4s ease 0.16s both; }}
  .section-label {{ animation: fadeIn 0.4s ease 0.22s both; }}
  .pages         {{ animation: fadeIn 0.4s ease 0.26s both; }}
</style>
</head>
<body>
  <div class="content">
    <div class="error-code">404</div>
    <div class="title">Page Not Found</div>
    <div class="message"><code>{safe_url}</code> is not a recognized internal page.</div>
    <div class="section-label">Available Pages</div>
    <div class="pages">
      {page_links}
    </div>
  </div>
</body>
</html>"""
