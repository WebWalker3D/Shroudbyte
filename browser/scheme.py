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
    ACCENT, ACCENT_HOVER, ACCENT_TEXT, BG_DARK, BG_CARD,
    TEXT, TEXT_DIM, TEXT_FAINT, BORDER,
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
    "about": "About Shroudbyte",
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
        elif host == "about":
            html = self._page_about()
        else:
            html = self._page_error(url.toString())

        buf = QBuffer(parent=job)
        buf.setData(html.encode("utf-8"))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(b"text/html", buf)

    # ── Page generators ──────────────────────────────────────────

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

        os_info = f"{platform.system()} {platform.release()}"
        arch = platform.machine()
        profile_path = str(storage.DATA_DIR)

        rows = [
            ("Python", py_ver),
            ("Qt", qt_ver),
            ("PyQt6", pyqt_ver),
            ("Chromium", chromium_ver),
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
