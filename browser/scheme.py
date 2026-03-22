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

    # ── Page generators ──────────────────────────────────────────

    def _page_bookmarks(self):
        """Generate the shroud://bookmarks page."""
        bookmarks = storage.load_bookmarks()

        rows = ""
        for bm in bookmarks:
            esc_url = html_mod.escape(bm.get("url", ""))
            esc_title = html_mod.escape(bm.get("title", esc_url)[:80])
            rows += f"""
      <div class="entry">
        <a href="{esc_url}" class="entry-link">
          <div class="entry-title">{esc_title}</div>
          <div class="entry-url">{esc_url}</div>
        </a>
        <button class="act-btn danger" onclick="pageAct('del_bookmark','{esc_url}')">Delete</button>
      </div>"""

        if not bookmarks:
            rows = '<div class="empty">No bookmarks yet. Press Ctrl+D to bookmark a page.</div>'

        page_links = "\n      ".join(
            f'<a href="shroud://{n}">shroud://{n}</a>' for n in _PAGES
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bookmarks &mdash; {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; padding-top: 8vh; padding-bottom: 8vh;
  }}
  .bg-glow {{
    position: fixed; top: 14%; left: 50%;
    transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(ellipse, rgba(205, 141, 106, 0.04) 0%, transparent 65%);
    pointer-events: none; z-index: 0;
  }}
  .content {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    width: 100%; max-width: 680px; padding: 0 24px;
  }}
  .wordmark {{
    font-size: 28px; font-weight: 700;
    letter-spacing: 6px; text-transform: uppercase; text-indent: 6px;
    background: linear-gradient(135deg, {ACCENT_HOVER} 0%, {ACCENT} 35%, {ACCENT_TEXT} 65%, {ACCENT} 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; user-select: none;
  }}
  .subtitle {{ font-size: 11px; color: {TEXT_FAINT}; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 32px; }}
  .card {{
    width: 100%; background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 12px; padding: 4px 0; margin-bottom: 24px; overflow: hidden;
  }}
  .entry {{
    display: flex; align-items: center; padding: 10px 18px; gap: 12px;
  }}
  .entry + .entry {{ border-top: 1px solid {BORDER}; }}
  .entry-link {{
    flex: 1; min-width: 0; text-decoration: none;
    transition: opacity 0.15s;
  }}
  .entry-link:hover {{ opacity: 0.8; }}
  .entry-title {{ font-size: 13px; color: {TEXT}; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .entry-url {{ font-size: 11px; color: {TEXT_FAINT}; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .act-btn {{
    padding: 4px 12px; font-size: 11px; font-weight: 500;
    border: 1px solid {BORDER}; border-radius: 5px;
    background: {BG_MID}; color: {TEXT_DIM}; cursor: pointer;
    font-family: inherit; flex-shrink: 0;
  }}
  .act-btn:hover {{ background: {ACCENT}; border-color: {ACCENT}; color: {BG_DARK}; }}
  .act-btn.danger {{ border-color: {RED}; color: {RED}; background: transparent; }}
  .act-btn.danger:hover {{ background: {RED}; color: {BG_DARK}; }}
  .empty {{ text-align: center; padding: 40px 20px; color: {TEXT_FAINT}; font-size: 14px; }}
  .stat {{ font-size: 12px; color: {TEXT_DIM}; margin-bottom: 16px; }}
  .footer {{ margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }}
  .footer a {{ padding: 8px 16px; background: rgba(28,27,36,0.6); border: 1px solid rgba(40,38,51,0.5); border-radius: 8px; text-decoration: none; color: {ACCENT}; font-size: 13px; font-family: 'JetBrains Mono', monospace; transition: all 0.2s; }}
  .footer a:hover {{ background: rgba(38,36,48,0.85); border-color: rgba(205,141,106,0.3); transform: translateY(-1px); }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .wordmark {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .subtitle {{ animation: fadeIn 0.5s ease 0.10s both; }}
  .card {{ animation: fadeIn 0.5s ease 0.18s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="content">
    <div class="wordmark">Bookmarks</div>
    <div class="subtitle">{len(bookmarks)} saved</div>
    <div class="card">{rows}</div>
    <div class="footer">{page_links}</div>
  </div>
  <script>
    function pageAct(action, arg) {{
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({{action:action,arg:arg}}));
      setTimeout(function(){{ location.reload(); }}, 200);
    }}
  </script>
</body>
</html>"""

    def _page_history(self):
        """Generate the shroud://history page with client-side filtering."""
        import time as _time
        history = storage.load_history()

        rows_js = []
        for h in history[:2000]:
            ts = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(h.get("visited", 0)))
            esc_url = html_mod.escape(h.get("url", ""))
            esc_title = html_mod.escape(h.get("title", "")[:80])
            rows_js.append(
                f'{{"t":"{esc_title}","u":"{esc_url}","d":"{ts}"}}'
            )

        history_json = "[" + ",\n".join(rows_js) + "]"

        page_links = "\n      ".join(
            f'<a href="shroud://{n}">shroud://{n}</a>' for n in _PAGES
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>History &mdash; {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; padding-top: 8vh; padding-bottom: 8vh;
  }}
  .bg-glow {{
    position: fixed; top: 14%; left: 50%; transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(ellipse, rgba(205, 141, 106, 0.04) 0%, transparent 65%);
    pointer-events: none; z-index: 0;
  }}
  .content {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    width: 100%; max-width: 680px; padding: 0 24px;
  }}
  .wordmark {{
    font-size: 28px; font-weight: 700; letter-spacing: 6px;
    text-transform: uppercase; text-indent: 6px;
    background: linear-gradient(135deg, {ACCENT_HOVER} 0%, {ACCENT} 35%, {ACCENT_TEXT} 65%, {ACCENT} 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; user-select: none;
  }}
  .subtitle {{ font-size: 11px; color: {TEXT_FAINT}; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 24px; }}
  .search {{
    width: 100%; padding: 10px 16px; font-size: 14px;
    background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 10px; margin-bottom: 16px; font-family: inherit;
  }}
  .search:focus {{ border-color: {ACCENT}; outline: none; }}
  .actions-bar {{
    display: flex; justify-content: flex-end; width: 100%; margin-bottom: 12px;
  }}
  .card {{
    width: 100%; background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 12px; padding: 4px 0; margin-bottom: 24px; overflow: hidden;
    max-height: 70vh; overflow-y: auto;
  }}
  .entry {{
    display: flex; align-items: center; padding: 8px 18px; gap: 12px;
  }}
  .entry + .entry {{ border-top: 1px solid {BORDER}; }}
  .entry-link {{
    flex: 1; min-width: 0; text-decoration: none;
  }}
  .entry-link:hover .entry-title {{ color: {ACCENT}; }}
  .entry-title {{ font-size: 13px; color: {TEXT}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; transition: color 0.15s; }}
  .entry-url {{ font-size: 10px; color: {TEXT_FAINT}; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .entry-date {{ font-size: 10px; color: {TEXT_FAINT}; flex-shrink: 0; }}
  .act-btn {{
    padding: 4px 12px; font-size: 11px; font-weight: 500;
    border: 1px solid {BORDER}; border-radius: 5px;
    background: {BG_MID}; color: {TEXT_DIM}; cursor: pointer;
    font-family: inherit;
  }}
  .act-btn:hover {{ background: {ACCENT}; border-color: {ACCENT}; color: {BG_DARK}; }}
  .act-btn.danger {{ border-color: {RED}; color: {RED}; background: transparent; }}
  .act-btn.danger:hover {{ background: {RED}; color: {BG_DARK}; }}
  .empty {{ text-align: center; padding: 40px 20px; color: {TEXT_FAINT}; font-size: 14px; }}
  .footer {{ margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }}
  .footer a {{ padding: 8px 16px; background: rgba(28,27,36,0.6); border: 1px solid rgba(40,38,51,0.5); border-radius: 8px; text-decoration: none; color: {ACCENT}; font-size: 13px; font-family: 'JetBrains Mono', monospace; transition: all 0.2s; }}
  .footer a:hover {{ background: rgba(38,36,48,0.85); border-color: rgba(205,141,106,0.3); transform: translateY(-1px); }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .wordmark {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .card {{ animation: fadeIn 0.5s ease 0.18s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="content">
    <div class="wordmark">History</div>
    <div class="subtitle">{len(history)} entries</div>
    <input class="search" type="text" placeholder="Filter history..." oninput="filterHistory(this.value)">
    <div class="actions-bar">
      <button class="act-btn danger" onclick="if(confirm('Clear all history?'))pageAct('clear_history','')">Clear All History</button>
    </div>
    <div class="card" id="historyList"></div>
    <div class="footer">{page_links}</div>
  </div>
  <script>
    var _history = {history_json};

    function esc(s) {{ var d = document.createElement('span'); d.textContent = s; return d.innerHTML; }}

    function renderHistory(items) {{
      var el = document.getElementById('historyList');
      if (!items.length) {{ el.innerHTML = '<div class="empty">No matching history.</div>'; return; }}
      var h = '';
      for (var i = 0; i < items.length && i < 500; i++) {{
        var e = items[i];
        h += '<div class="entry">' +
          '<a class="entry-link" href="' + e.u + '">' +
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

    renderHistory(_history);
  </script>
</body>
</html>"""

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
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; padding-top: 8vh; padding-bottom: 8vh;
  }}
  .bg-glow {{
    position: fixed; top: 14%; left: 50%;
    transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(ellipse, rgba(205, 141, 106, 0.04) 0%, transparent 65%);
    pointer-events: none; z-index: 0;
  }}
  .content {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    width: 100%; max-width: 600px; padding: 0 24px;
  }}
  .wordmark {{
    font-size: 28px; font-weight: 700;
    letter-spacing: 6px; text-transform: uppercase; text-indent: 6px;
    background: linear-gradient(
      135deg, {ACCENT_HOVER} 0%, {ACCENT} 35%, {ACCENT_TEXT} 65%, {ACCENT} 100%
    );
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; user-select: none;
  }}
  .subtitle {{
    font-size: 11px; color: {TEXT_FAINT};
    letter-spacing: 3px; text-transform: uppercase;
    margin-bottom: 32px;
  }}
  .section {{ width: 100%; margin-bottom: 20px; }}
  .section h2 {{
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 3px; color: {TEXT_FAINT};
    font-weight: 600; margin-bottom: 10px; padding-left: 4px;
  }}
  .card {{
    width: 100%; background: {BG_CARD};
    border: 1px solid {BORDER}; border-radius: 12px;
    padding: 6px 20px; overflow: hidden;
  }}
  .row {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 0; gap: 16px;
  }}
  .row + .row {{ border-top: 1px solid {BORDER}; }}
  .row-label {{
    font-size: 13px; color: {TEXT_DIM}; min-width: 160px; flex-shrink: 0;
  }}
  .row-hint {{
    font-size: 10px; color: {TEXT_FAINT}; margin-top: 2px;
  }}
  input[type="text"], input[type="number"], select {{
    padding: 8px 12px; font-size: 13px;
    background: {BG_DARK}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    font-family: inherit; flex: 1; min-width: 0;
  }}
  input[type="text"]:focus, input[type="number"]:focus, select:focus {{
    border-color: {ACCENT}; outline: none;
  }}
  input[type="text"]:read-only {{
    opacity: 0.5; cursor: not-allowed;
  }}
  select {{ cursor: pointer; }}
  select option {{ background: {BG_CARD}; color: {TEXT}; }}

  /* Toggle switch */
  .toggle {{ position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }}
  .toggle input {{ opacity: 0; width: 0; height: 0; }}
  .toggle .slider {{
    position: absolute; cursor: pointer; inset: 0;
    background: {BG_ACTIVE}; border-radius: 22px;
    transition: 0.2s;
  }}
  .toggle .slider:before {{
    content: ""; position: absolute;
    height: 16px; width: 16px; left: 3px; bottom: 3px;
    background: {TEXT_FAINT}; border-radius: 50%;
    transition: 0.2s;
  }}
  .toggle input:checked + .slider {{ background: {ACCENT}; }}
  .toggle input:checked + .slider:before {{
    transform: translateX(18px); background: {BG_DARK};
  }}

  .save-bar {{
    position: sticky; bottom: 0;
    width: 100%; padding: 16px 0;
    display: flex; justify-content: center; gap: 12px;
    background: linear-gradient(transparent, {BG_DARK} 30%);
  }}
  .btn {{
    padding: 10px 28px; font-size: 13px; font-weight: 600;
    border: none; border-radius: 8px; cursor: pointer;
    font-family: inherit; transition: all 0.15s ease;
  }}
  .btn-primary {{
    background: {ACCENT}; color: {BG_DARK};
  }}
  .btn-primary:hover {{ background: {ACCENT_HOVER}; }}
  .btn-secondary {{
    background: {BG_CARD}; color: {TEXT};
    border: 1px solid {BORDER};
  }}
  .btn-secondary:hover {{ background: {BG_HOVER}; border-color: {ACCENT}; }}
  .btn-danger {{
    background: transparent; color: {RED};
    border: 1px solid {RED};
  }}
  .btn-danger:hover {{ background: {RED}; color: {BG_DARK}; }}
  .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}
  .dns-status {{
    font-size: 11px; padding: 4px 10px;
    border-radius: 4px;
  }}
  .dns-row {{ display: flex; gap: 8px; align-items: center; flex: 1; min-width: 0; }}
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
  .restart-note {{
    font-size: 10px; color: {YELLOW}; margin-top: 2px;
  }}
  .footer {{
    margin-top: 16px;
    display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;
  }}
  .footer a {{
    padding: 8px 16px;
    background: rgba(28, 27, 36, 0.6);
    border: 1px solid rgba(40, 38, 51, 0.5);
    border-radius: 8px; text-decoration: none;
    color: {ACCENT}; font-size: 13px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    transition: all 0.2s ease;
  }}
  .footer a:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
    transform: translateY(-1px);
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .wordmark  {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .subtitle  {{ animation: fadeIn 0.5s ease 0.10s both; }}
  .section   {{ animation: fadeIn 0.5s ease 0.18s both; }}
  .save-bar  {{ animation: fadeIn 0.5s ease 0.26s both; }}
  .footer    {{ animation: fadeIn 0.5s ease 0.30s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="content">
    <div class="wordmark">Settings</div>
    <div class="subtitle">Browser Configuration</div>

    <div class="section">
      <h2>General</h2>
      <div class="card">
        <div class="row">
          <div class="row-label">Search Engine</div>
          <div style="flex:1;display:flex;flex-direction:column;gap:6px;">
            <select id="search_preset" onchange="applyPreset(this.value)"
              style="padding:8px 12px;font-size:13px;background:{BG_DARK};color:{TEXT};border:1px solid {BORDER};border-radius:8px;cursor:pointer;font-family:inherit;">
              <option value="">Custom URL</option>
              <optgroup label="Private">
              <option value="https://duckduckgo.com/?q={{}}">DuckDuckGo — no tracking, US-based</option>
              <option value="https://www.startpage.com/sp/search?query={{}}">Startpage — Google results without tracking</option>
              <option value="https://search.brave.com/search?q={{}}">Brave Search — independent index, no tracking</option>
              <option value="https://www.mojeek.com/search?q={{}}">Mojeek — own crawler, UK-based, no tracking</option>
              <option value="https://www.qwant.com/?q={{}}">Qwant — EU-based, GDPR-native privacy</option>
              <option value="https://www.ecosia.org/search?q={{}}">Ecosia — plants trees, privacy-respecting</option>
              </optgroup>
              <optgroup label="Power User">
              <option value="https://kagi.com/search?q={{}}">Kagi — paid, no ads, excellent results</option>
              <option value="https://search.marginalia.nu/search?query={{}}">Marginalia — indie sites, non-commercial web</option>
              <option value="https://wiby.me/?q={{}}">Wiby — lightweight/personal sites, old-school web</option>
              </optgroup>
              <optgroup label="Standard (trackers blocked by Shroudbyte)">
              <option value="https://www.google.com/search?q={{}}">Google — best results, tracking blocked by browser</option>
              <option value="https://www.bing.com/search?q={{}}">Bing — Microsoft search, tracking blocked by browser</option>
              <option value="https://search.yahoo.com/search?p={{}}">Yahoo — Bing-powered, tracking blocked by browser</option>
              <option value="https://yandex.com/search/?text={{}}">Yandex — Russian search engine, tracking blocked by browser</option>
              </optgroup>
            </select>
            <input type="text" id="search_engine"
              value="{html_mod.escape(settings.get('search_engine', ''))}"
              placeholder="https://duckduckgo.com/?q={{}}"
              style="font-size:12px;font-family:monospace;">
          </div>
        </div>
        <div class="row">
          <div class="row-label">Default Zoom</div>
          <input type="number" id="default_zoom" min="25" max="500"
            value="{settings.get('default_zoom', 100)}" style="width:90px;flex:none"> %
        </div>
        <div class="row">
          <div class="row-label">User Agent</div>
          <input type="text" id="user_agent"
            value="{html_mod.escape(settings.get('user_agent', ''))}"
            placeholder="Leave blank for default">
        </div>
        <div class="row">
          <div class="row-label">JavaScript</div>
          <label class="toggle"><input type="checkbox" id="enable_javascript"
            {_chk('enable_javascript', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Restore Session</div>
          <label class="toggle"><input type="checkbox" id="restore_session"
            {_chk('restore_session', True)}><span class="slider"></span></label>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>Privacy</h2>
      <div class="card">
        <div class="row">
          <div class="row-label">Ad Blocker</div>
          <label class="toggle"><input type="checkbox" id="enable_adblock"
            {_chk('enable_adblock', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">HTTPS-Only Mode</div>
          <label class="toggle"><input type="checkbox" id="https_only"
            {_chk('https_only')}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Do Not Track</div>
          <label class="toggle"><input type="checkbox" id="do_not_track"
            {_chk('do_not_track', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Strip Tracking Params</div>
          <label class="toggle"><input type="checkbox" id="strip_tracking"
            {_chk('strip_tracking', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Fingerprint Resistance</div>
          <label class="toggle"><input type="checkbox" id="fingerprint_resistance"
            {_chk('fingerprint_resistance')}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Link Intelligence</div>
          <label class="toggle"><input type="checkbox" id="link_intelligence"
            {_chk('link_intelligence', True)}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Auto-Delete Cookies
            <div class="row-hint">Delete cookies when you leave a site</div>
          </div>
          <label class="toggle"><input type="checkbox" id="auto_delete_cookies"
            {_chk('auto_delete_cookies')}><span class="slider"></span></label>
        </div>
        <div class="row">
          <div class="row-label">Page Watch Interval</div>
          <input type="number" id="page_watch_interval" min="1" max="1440"
            value="{settings.get('page_watch_interval', 3600) // 60}"
            style="width:80px;flex:none"> min
        </div>
        <div class="row">
          <div class="row-label">Remember Scroll Position
            <div class="row-hint">Resume reading where you left off</div>
          </div>
          <label class="toggle"><input type="checkbox" id="remember_scroll_position"
            {_chk('remember_scroll_position', True)}><span class="slider"></span></label>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>DNS</h2>
      <div class="card">
        <div class="row">
          <div class="row-label">DNS-over-HTTPS
            <div class="restart-note">Changes require restart</div>
          </div>
          <select id="dns_over_https" {dns_disabled}>{doh_options}</select>
        </div>
        <div class="row">
          <div class="row-label">DoH Provider URL</div>
          <input type="text" id="dns_over_https_provider" {dns_disabled}
            value="{html_mod.escape(settings.get('dns_over_https_provider', ''))}"
            placeholder="https://dns.cloudflare.com/dns-query">
        </div>
      </div>
    </div>

    <div class="section">
      <h2>Shroud DNS</h2>
      <div class="card">
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
          <div class="row-label">Fallback to system DNS</div>
          <label class="toggle"><input type="checkbox" id="custom_dns_fallback"
            {_chk('custom_dns_fallback', True)}><span class="slider"></span></label>
        </div>
      </div>
    </div>

    <div class="save-bar">
      <button class="btn btn-primary" onclick="saveSettings()">Save Settings</button>
    </div>

    <div class="footer">
      {page_links}
    </div>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    function applyPreset(url) {{
      if (url) document.getElementById('search_engine').value = url;
    }}
    // Auto-select matching preset on load
    (function() {{
      var cur = document.getElementById('search_engine').value;
      var sel = document.getElementById('search_preset');
      for (var i = 0; i < sel.options.length; i++) {{
        if (sel.options[i].value && cur.indexOf(sel.options[i].value.split('?')[0]) !== -1) {{
          sel.selectedIndex = i; break;
        }}
      }}
    }})();

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

        page_links = "\n      ".join(
            f'<a href="shroud://{name}">shroud://{name}</a>'
            for name in _PAGES
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Page Watches &mdash; {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; padding-top: 8vh; padding-bottom: 8vh;
  }}
  .bg-glow {{
    position: fixed; top: 14%; left: 50%;
    transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(ellipse, rgba(205, 141, 106, 0.04) 0%, transparent 65%);
    pointer-events: none; z-index: 0;
  }}
  .content {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    width: 100%; max-width: 680px; padding: 0 24px;
  }}
  .wordmark {{
    font-size: 28px; font-weight: 700;
    letter-spacing: 6px; text-transform: uppercase; text-indent: 6px;
    background: linear-gradient(
      135deg, {ACCENT_HOVER} 0%, {ACCENT} 35%, {ACCENT_TEXT} 65%, {ACCENT} 100%
    );
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; user-select: none;
  }}
  .subtitle {{
    font-size: 11px; color: {TEXT_FAINT};
    letter-spacing: 3px; text-transform: uppercase;
    margin-bottom: 32px;
  }}
  .overview {{
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 12px; width: 100%; margin-bottom: 32px;
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
  .dot {{
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
  }}
  .dot.green {{ background: {GREEN}; }}
  .dot.dim {{ background: {TEXT_FAINT}; }}
  .act-btn {{
    padding: 4px 12px; font-size: 11px; font-weight: 500;
    border: 1px solid {BORDER}; border-radius: 5px;
    background: {BG_MID}; color: {TEXT_DIM};
    cursor: pointer; transition: all 0.15s ease;
    font-family: inherit; text-decoration: none;
    display: inline-block;
  }}
  .act-btn:hover {{
    background: {ACCENT}; border-color: {ACCENT}; color: {BG_DARK};
  }}
  .act-btn.danger {{ border-color: {RED}; color: {RED}; background: transparent; }}
  .act-btn.danger:hover {{ background: {RED}; color: {BG_DARK}; }}
  .act-btn.visit {{ border-color: {GREEN}; color: {GREEN}; background: transparent; }}
  .act-btn.visit:hover {{ background: {GREEN}; color: {BG_DARK}; }}
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
  .diff-ctx {{ color: {TEXT_FAINT}; }}
  .empty {{
    text-align: center; padding: 40px 20px;
    color: {TEXT_FAINT}; font-size: 14px;
  }}
  .footer {{
    margin-top: 24px;
    display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;
  }}
  .footer a {{
    padding: 8px 16px;
    background: rgba(28, 27, 36, 0.6);
    border: 1px solid rgba(40, 38, 51, 0.5);
    border-radius: 8px; text-decoration: none;
    color: {ACCENT}; font-size: 13px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    transition: all 0.2s ease;
  }}
  .footer a:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
    transform: translateY(-1px);
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .wordmark    {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .subtitle    {{ animation: fadeIn 0.5s ease 0.10s both; }}
  .overview    {{ animation: fadeIn 0.5s ease 0.18s both; }}
  .watch-card  {{ animation: fadeIn 0.4s ease 0.26s both; }}
  .footer      {{ animation: fadeIn 0.5s ease 0.34s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="content">
    <div class="wordmark">Watches</div>
    <div class="subtitle">Page Change Monitor</div>

    <div class="overview">
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

    {cards}

    <div class="footer">
      {page_links}
    </div>
  </div>

  <script>
    function watchAct(action, url, extra) {{
      console.log('__SHROUD_WATCH__:' + JSON.stringify({{
        action: action, url: url || '', interval: extra || ''
      }}));
      setTimeout(function() {{ location.reload(); }}, 300);
    }}
  </script>
</body>
</html>"""

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

        page_links = "\n      ".join(
            f'<a href="shroud://{name}">shroud://{name}</a>'
            for name in _PAGES
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Privacy Dashboard &mdash; {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; padding-top: 8vh; padding-bottom: 8vh;
  }}
  .bg-glow {{
    position: fixed; top: 14%; left: 50%;
    transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(ellipse, rgba(205, 141, 106, 0.04) 0%, transparent 65%);
    pointer-events: none; z-index: 0;
  }}
  .content {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    width: 100%; max-width: 680px; padding: 0 24px;
  }}
  .wordmark {{
    font-size: 28px; font-weight: 700;
    letter-spacing: 6px; text-transform: uppercase; text-indent: 6px;
    background: linear-gradient(
      135deg, {ACCENT_HOVER} 0%, {ACCENT} 35%, {ACCENT_TEXT} 65%, {ACCENT} 100%
    );
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; user-select: none;
  }}
  .subtitle {{
    font-size: 11px; color: {TEXT_FAINT};
    letter-spacing: 3px; text-transform: uppercase;
    margin-bottom: 32px;
  }}

  /* Overview cards */
  .overview {{
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 12px; width: 100%; margin-bottom: 32px;
  }}
  .stat-card {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 16px; text-align: center;
  }}
  .stat-num {{
    font-size: 28px; font-weight: 700;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
  }}
  .stat-num.blocked {{ color: {RED}; }}
  .stat-num.third-party {{ color: {YELLOW}; }}
  .stat-num.stripped {{ color: {ACCENT}; }}
  .stat-num.cookies {{ color: {GREEN}; }}
  .stat-label {{
    font-size: 10px; color: {TEXT_FAINT};
    text-transform: uppercase; letter-spacing: 1px;
    margin-top: 4px;
  }}

  /* Sections */
  .section {{
    width: 100%; margin-bottom: 24px;
  }}
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

  /* Site cards */
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

  /* Request table */
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

  .dot {{
    display: inline-block; width: 8px; height: 8px;
    border-radius: 50%;
  }}
  .dot.red {{ background: {RED}; }}
  .dot.green {{ background: {GREEN}; }}
  .dot.yellow {{ background: {YELLOW}; }}

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

  .empty {{
    text-align: center; padding: 40px 20px;
    color: {TEXT_FAINT}; font-size: 14px;
  }}

  /* Action buttons */
  .act-cell {{ text-align: right; width: 80px; }}
  .act-btn {{
    padding: 3px 10px; font-size: 11px; font-weight: 500;
    border: 1px solid {BORDER}; border-radius: 5px;
    background: {BG_MID}; color: {TEXT_DIM};
    cursor: pointer; transition: all 0.15s ease;
    font-family: inherit;
  }}
  .act-btn:hover {{
    background: {ACCENT}; border-color: {ACCENT};
    color: {BG_DARK};
  }}
  .act-btn.danger {{ border-color: {RED}; color: {RED}; background: transparent; }}
  .act-btn.danger:hover {{ background: {RED}; color: {BG_DARK}; }}
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
  .reload-banner button:hover {{ background: {ACCENT_HOVER}; }}

  .footer {{
    margin-top: 16px;
    display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;
  }}
  .footer a {{
    padding: 8px 16px;
    background: rgba(28, 27, 36, 0.6);
    border: 1px solid rgba(40, 38, 51, 0.5);
    border-radius: 8px; text-decoration: none;
    color: {ACCENT}; font-size: 13px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    transition: all 0.2s ease;
  }}
  .footer a:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
    transform: translateY(-1px);
  }}

  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .wordmark  {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .subtitle  {{ animation: fadeIn 0.5s ease 0.10s both; }}
  .overview  {{ animation: fadeIn 0.5s ease 0.18s both; }}
  .section   {{ animation: fadeIn 0.5s ease 0.26s both; }}
  .site-card {{ animation: fadeIn 0.4s ease 0.30s both; }}
  .footer    {{ animation: fadeIn 0.5s ease 0.40s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="content">
    <div class="wordmark">Privacy</div>
    <div class="subtitle">Privacy Dashboard</div>

    <div class="overview">
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

    <div class="footer">
      {page_links}
    </div>
  </div>

  <div class="reload-banner" id="reloadBanner">
    Changes saved. Reload affected tabs for them to take effect.
    <button onclick="location.reload()">Refresh dashboard</button>
  </div>

  <script>
    function privacyAct(action, arg1, arg2) {{
      console.log('__SHROUD_PRIVACY__:' + JSON.stringify({{
        action: action, arg1: arg1 || '', arg2: arg2 || ''
      }}));
      // Show reload banner and refresh page after Python processes
      document.getElementById('reloadBanner').style.display = 'block';
      setTimeout(function() {{ location.reload(); }}, 200);
    }}
  </script>
</body>
</html>"""

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

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>About {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; padding-top: 16vh;
  }}
  .bg-glow {{
    position: fixed; top: 18%; left: 50%;
    transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(ellipse, rgba(205, 141, 106, 0.04) 0%, transparent 65%);
    pointer-events: none; z-index: 0;
  }}
  .content {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    width: 100%; max-width: 520px; padding: 0 24px;
  }}
  .wordmark {{
    font-size: 32px; font-weight: 700;
    letter-spacing: 8px; text-transform: uppercase; text-indent: 8px;
    background: linear-gradient(
      135deg, {ACCENT_HOVER} 0%, {ACCENT} 35%, {ACCENT_TEXT} 65%, {ACCENT} 100%
    );
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; user-select: none;
  }}
  .version {{
    font-size: 11px; color: {TEXT_FAINT};
    letter-spacing: 3px; text-transform: uppercase;
    margin-bottom: 40px;
  }}
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
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .wordmark      {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .version       {{ animation: fadeIn 0.5s ease 0.10s both; }}
  .info-card     {{ animation: fadeIn 0.5s ease 0.18s both; }}
  .section-label {{ animation: fadeIn 0.5s ease 0.26s both; }}
  .pages         {{ animation: fadeIn 0.5s ease 0.30s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="content">
    <div class="wordmark">Shroudbyte</div>
    <div class="version">Version {__version__}</div>
    <div class="info-card">
      <table>
{table_rows}
      </table>
    </div>
    <div class="section-label">Internal Pages</div>
    <div class="pages">
      {page_links}
    </div>
  </div>
</body>
</html>"""

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
        anim_delay = 0.18
        for cat_name, shortcuts in categories:
            rows = "\n".join(
                f'              <tr>'
                f'<td class="key"><kbd>{html_mod.escape(key)}</kbd></td>'
                f'<td class="desc">{html_mod.escape(desc)}</td>'
                f'</tr>'
                for key, desc in shortcuts
            )
            sections_html += f"""
    <div class="category" style="animation-delay: {anim_delay:.2f}s;">
      <h2>{html_mod.escape(cat_name)}</h2>
      <div class="info-card">
        <table>
{rows}
        </table>
      </div>
    </div>"""
            anim_delay += 0.08

        page_links = "\n      ".join(
            f'<a href="shroud://{name}">shroud://{name}</a>'
            for name in _PAGES
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Keyboard Shortcuts \u2014 {__app_name__}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK}; color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; padding-top: 10vh; padding-bottom: 8vh;
  }}
  .bg-glow {{
    position: fixed; top: 14%; left: 50%;
    transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(ellipse, rgba(205, 141, 106, 0.04) 0%, transparent 65%);
    pointer-events: none; z-index: 0;
  }}
  .content {{
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    width: 100%; max-width: 600px; padding: 0 24px;
  }}
  .wordmark {{
    font-size: 28px; font-weight: 700;
    letter-spacing: 6px; text-transform: uppercase; text-indent: 6px;
    background: linear-gradient(
      135deg, {ACCENT_HOVER} 0%, {ACCENT} 35%, {ACCENT_TEXT} 65%, {ACCENT} 100%
    );
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; user-select: none;
  }}
  .subtitle {{
    font-size: 11px; color: {TEXT_FAINT};
    letter-spacing: 3px; text-transform: uppercase;
    margin-bottom: 40px;
  }}
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
  }}
  .footer {{
    margin-top: 16px;
    display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;
  }}
  .footer a {{
    padding: 8px 16px;
    background: rgba(28, 27, 36, 0.6);
    border: 1px solid rgba(40, 38, 51, 0.5);
    border-radius: 8px; text-decoration: none;
    color: {ACCENT}; font-size: 13px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    transition: all 0.2s ease;
  }}
  .footer a:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
    transform: translateY(-1px);
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .wordmark  {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .subtitle  {{ animation: fadeIn 0.5s ease 0.10s both; }}
  .category  {{ animation: fadeIn 0.5s ease both; }}
  .footer    {{ animation: fadeIn 0.5s ease 0.60s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <div class="content">
    <div class="wordmark">Shortcuts</div>
    <div class="subtitle">Keyboard shortcuts</div>
{sections_html}
    <div class="footer">
      {page_links}
    </div>
  </div>
</body>
</html>"""

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
