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
    ACCENT, ACCENT_HOVER, ACCENT_TEXT, BG_DARK, BG_CARD, BG_MID,
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

    # ── Page generators ──────────────────────────────────────────

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
