"""Custom shroud:// URL scheme handler for internal browser pages."""

import html as html_mod
import os
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
    "saved": "Saved Pages",
    "apps": "Installed Apps",
    "permissions": "Permission Ledger",
    "background": "Background Activity",
    "captures": "Captures",
    "extensions": "Extensions",
    "profiles": "Profiles",
    "sessions": "Sessions",
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
        elif host == "saved":
            html = self._page_saved()
        elif host == "apps":
            html = self._page_apps()
        elif host == "permissions":
            html = self._page_permissions()
        elif host == "background":
            html = self._page_background()
        elif host == "captures":
            html = self._page_captures()
        elif host == "extensions":
            html = self._page_extensions()
        elif host == "profiles":
            html = self._page_profiles()
        elif host == "sessions":
            html = self._page_sessions()
        elif host == "savedview":
            html = self._page_saved_view(url)
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
        ("saved", "\u2B73", "Saved Pages"),
        ("apps", "\u2B1A", "Apps"),
        ("permissions", "\u2263", "Permissions"),
        ("background", "\u2B6E", "Background"),
        ("captures", "\u23fa", "Captures"),
        ("extensions", "\u29C9", "Extensions"),
        ("profiles", "\u2B50", "Profiles"),
        ("sessions", "\u2630", "Sessions"),
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
        import json as _json
        bookmarks = storage.load_bookmarks()
        folders = storage.get_bookmark_folders()
        all_tags = storage.get_bookmark_tags()

        # Build JSON data for JS-side rendering
        bm_data = []
        for bm in bookmarks:
            bm_data.append({
                "title": bm.get("title", ""),
                "url": bm.get("url", ""),
                "folder": bm.get("folder", ""),
                "tags": bm.get("tags", []),
                "added": bm.get("added", 0),
            })
        bm_json = _json.dumps(bm_data)
        folders_json = _json.dumps(folders)
        tags_json = _json.dumps(all_tags)

        extra_css = f"""
    .bm-layout {{ display: flex; gap: 0; }}
    .bm-sidebar {{
      width: 180px; flex-shrink: 0;
      border-right: 1px solid {BORDER}; padding: 8px 0;
      max-height: 75vh; overflow-y: auto;
    }}
    .bm-folder {{
      display: block; padding: 7px 16px; font-size: 12px;
      color: {TEXT_DIM}; cursor: pointer; border: none;
      background: transparent; text-align: left; width: 100%;
      font-family: inherit; transition: all 0.12s;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .bm-folder:hover {{ color: {TEXT}; background: {BG_HOVER}; }}
    .bm-folder.active {{ color: {ACCENT}; background: rgba(205,141,106,0.08); }}
    .bm-folder .folder-icon {{ margin-right: 6px; font-size: 11px; }}
    .bm-content {{ flex: 1; min-width: 0; }}
    .tag-bar {{
      display: flex; flex-wrap: wrap; gap: 6px;
      padding: 10px 16px; border-bottom: 1px solid {BORDER};
    }}
    .tag-pill {{
      padding: 3px 10px; font-size: 11px; border-radius: 12px;
      border: 1px solid {BORDER}; background: {BG_MID};
      color: {TEXT_DIM}; cursor: pointer; font-family: inherit;
      transition: all 0.12s;
    }}
    .tag-pill:hover {{ border-color: {ACCENT}; color: {TEXT}; }}
    .tag-pill.active {{ background: {ACCENT}; color: {BG_DARK}; border-color: {ACCENT}; }}
    .bm-list {{ padding: 4px 0; }}
    .bm-entry {{
      display: flex; align-items: center; padding: 10px 18px; gap: 12px;
    }}
    .bm-entry + .bm-entry {{ border-top: 1px solid {BORDER}; }}
    .bm-meta {{ display: flex; gap: 6px; align-items: center; margin-top: 3px; flex-wrap: wrap; }}
    .bm-meta-folder {{
      font-size: 10px; color: {TEXT_FAINT};
      background: {BG_MID}; padding: 1px 7px; border-radius: 4px;
    }}
    .bm-meta-tag {{
      font-size: 10px; color: {ACCENT};
      background: rgba(205,141,106,0.1); padding: 1px 7px; border-radius: 4px;
    }}
    /* Edit dialog */
    .bm-overlay {{
      display: none; position: fixed; inset: 0; z-index: 200;
      background: rgba(0,0,0,0.6);
      justify-content: center; align-items: center;
    }}
    .bm-overlay.visible {{ display: flex; }}
    .bm-dialog {{
      background: {BG_CARD}; border: 1px solid {BORDER};
      border-radius: 14px; padding: 24px; width: 420px; max-width: 90vw;
    }}
    .bm-dialog h3 {{ font-size: 16px; margin-bottom: 16px; color: {TEXT}; }}
    .bm-dialog label {{ display: block; font-size: 12px; color: {TEXT_DIM}; margin: 10px 0 4px; }}
    .bm-dialog input[type="text"] {{ width: 100%; }}
    .bm-dialog .dialog-btns {{ display: flex; gap: 8px; justify-content: flex-end; margin-top: 18px; }}
"""

        content = f"""
    <div class="section-desc"><span id="bmCount">{len(bookmarks)}</span> saved</div>
    <input class="search" type="text" id="bmSearch" placeholder="Search bookmarks..."
           oninput="filterBookmarks()">
    <div class="card bm-layout">
      <div class="bm-sidebar" id="folderSidebar"></div>
      <div class="bm-content">
        <div class="tag-bar" id="tagBar"></div>
        <div class="bm-list" id="bmList"></div>
      </div>
    </div>

    <!-- Edit dialog -->
    <div class="bm-overlay" id="editOverlay" onclick="if(event.target===this)closeEdit()">
      <div class="bm-dialog">
        <h3>Edit Bookmark</h3>
        <input type="hidden" id="editUrl">
        <label>Title</label>
        <input type="text" id="editTitle">
        <label>Folder</label>
        <input type="text" id="editFolder" placeholder="e.g. Work / Research" list="folderList">
        <datalist id="folderList"></datalist>
        <label>Tags (comma-separated)</label>
        <input type="text" id="editTags" placeholder="e.g. news, tech, reference">
        <div class="dialog-btns">
          <button class="act-btn" onclick="closeEdit()">Cancel</button>
          <button class="act-btn visit" onclick="saveEdit()">Save</button>
        </div>
      </div>
    </div>"""

        extra_js = f"""
    var _bookmarks = {bm_json};
    var _folders = {folders_json};
    var _allTags = {tags_json};
    var _activeFolder = null;
    var _activeTag = null;

    function esc(s) {{ var d = document.createElement('span'); d.textContent = s; return d.innerHTML; }}

    function buildFolderSidebar() {{
      var sb = document.getElementById('folderSidebar');
      var h = '<button class="bm-folder active" onclick="selectFolder(null,this)">' +
              '<span class="folder-icon">\\u2606</span>All Bookmarks</button>';
      for (var i = 0; i < _folders.length; i++) {{
        h += '<button class="bm-folder" onclick="selectFolder(\\'' +
             esc(_folders[i]).replace(/'/g, "\\\\'") + '\\',this)">' +
             '<span class="folder-icon">\\ud83d\\udcc1</span>' + esc(_folders[i]) + '</button>';
      }}
      sb.innerHTML = h;
    }}

    function buildTagBar() {{
      var tb = document.getElementById('tagBar');
      if (!_allTags.length) {{ tb.style.display = 'none'; return; }}
      var h = '';
      for (var i = 0; i < _allTags.length; i++) {{
        h += '<button class="tag-pill" onclick="selectTag(\\'' +
             esc(_allTags[i]).replace(/'/g, "\\\\'") + '\\',this)">' +
             esc(_allTags[i]) + '</button>';
      }}
      tb.innerHTML = h;
    }}

    function selectFolder(name, el) {{
      _activeFolder = name;
      document.querySelectorAll('.bm-folder').forEach(function(b) {{ b.classList.remove('active'); }});
      if (el) el.classList.add('active');
      filterBookmarks();
    }}

    function selectTag(name, el) {{
      if (_activeTag === name) {{
        _activeTag = null;
        el.classList.remove('active');
      }} else {{
        _activeTag = name;
        document.querySelectorAll('.tag-pill').forEach(function(b) {{ b.classList.remove('active'); }});
        el.classList.add('active');
      }}
      filterBookmarks();
    }}

    function filterBookmarks() {{
      var q = (document.getElementById('bmSearch').value || '').toLowerCase();
      var filtered = _bookmarks.filter(function(bm) {{
        if (_activeFolder !== null && (bm.folder || '') !== _activeFolder) return false;
        if (_activeTag && (!bm.tags || bm.tags.indexOf(_activeTag) === -1)) return false;
        if (q) {{
          var hay = (bm.title + ' ' + bm.url + ' ' + (bm.folder || '') + ' ' + (bm.tags || []).join(' ')).toLowerCase();
          if (hay.indexOf(q) === -1) return false;
        }}
        return true;
      }});
      renderBookmarks(filtered);
    }}

    function renderBookmarks(items) {{
      var el = document.getElementById('bmList');
      document.getElementById('bmCount').textContent = items.length;
      if (!items.length) {{
        el.innerHTML = '<div class="empty">No bookmarks match the current filters.</div>';
        return;
      }}
      var h = '';
      for (var i = 0; i < items.length; i++) {{
        var bm = items[i];
        var u = esc(bm.url);
        var t = esc((bm.title || bm.url).substring(0, 80));

        // Metadata badges
        var meta = '';
        if (bm.folder) meta += '<span class="bm-meta-folder">' + esc(bm.folder) + '</span>';
        if (bm.tags && bm.tags.length) {{
          for (var j = 0; j < bm.tags.length; j++) {{
            meta += '<span class="bm-meta-tag">' + esc(bm.tags[j]) + '</span>';
          }}
        }}
        var metaHtml = meta ? '<div class="bm-meta">' + meta + '</div>' : '';

        h += '<div class="bm-entry">' +
          '<a href="' + u + '" class="entry-link" style="flex:1;min-width:0;text-decoration:none;">' +
          '<div class="entry-title">' + t + '</div>' +
          '<div class="entry-url">' + u + '</div>' +
          metaHtml + '</a>' +
          '<button class="act-btn" onclick="openEdit(\\'' +
            u.replace(/'/g, "\\\\'") + '\\')">Edit</button>' +
          '<button class="act-btn danger" onclick="pageAct(\\'del_bookmark\\',\\'' +
            u.replace(/'/g, "\\\\'") + '\\')">Delete</button>' +
          '</div>';
      }}
      el.innerHTML = h;
    }}

    function pageAct(action, arg) {{
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({{action:action,arg:arg}}));
      setTimeout(function(){{ location.reload(); }}, 200);
    }}

    function openEdit(url) {{
      var bm = null;
      for (var i = 0; i < _bookmarks.length; i++) {{
        if (_bookmarks[i].url === url) {{ bm = _bookmarks[i]; break; }}
      }}
      if (!bm) return;
      document.getElementById('editUrl').value = bm.url;
      document.getElementById('editTitle').value = bm.title || '';
      document.getElementById('editFolder').value = bm.folder || '';
      document.getElementById('editTags').value = (bm.tags || []).join(', ');
      // Populate datalist with existing folders
      var dl = document.getElementById('folderList');
      dl.innerHTML = '';
      for (var i = 0; i < _folders.length; i++) {{
        var opt = document.createElement('option');
        opt.value = _folders[i];
        dl.appendChild(opt);
      }}
      document.getElementById('editOverlay').classList.add('visible');
    }}

    function closeEdit() {{
      document.getElementById('editOverlay').classList.remove('visible');
    }}

    function saveEdit() {{
      var url = document.getElementById('editUrl').value;
      var title = document.getElementById('editTitle').value;
      var folder = document.getElementById('editFolder').value.trim();
      var tagsRaw = document.getElementById('editTags').value;
      var tags = tagsRaw ? tagsRaw.split(',').map(function(t){{ return t.trim(); }}).filter(Boolean) : [];
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({{
        action: 'edit_bookmark', arg: url,
        title: title, folder: folder, tags: tags
      }}));
      closeEdit();
      setTimeout(function(){{ location.reload(); }}, 200);
    }}

    buildFolderSidebar();
    buildTagBar();
    filterBookmarks();
"""

        return self._wrap("Bookmarks", "bookmarks", content,
                          extra_css=extra_css, extra_js=extra_js)

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
        <div class="section-title">Permissions</div>
        <div class="row">
          <div class="row-label">Permission auto-expire
            <div class="row-hint">Days until granted site permissions expire and re-prompt (0 = never)</div>
          </div>
          <input type="number" id="permission_ttl_days" min="0" max="3650"
            value="{settings.get('permission_ttl_days', 30)}"
            style="width:80px;flex:none">&nbsp;days
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
        permission_ttl_days: getVal('permission_ttl_days'),
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

    def _page_saved(self):
        """Generate the shroud://saved offline reading list page."""
        import time as _time
        pages = storage.load_saved_pages()

        def _ago(ts):
            d = _time.time() - ts
            if d < 60: return "just now"
            if d < 3600: return f"{int(d/60)}m ago"
            if d < 86400: return f"{int(d/3600)}h ago"
            return f"{int(d/86400)}d ago"

        def _size(b):
            if b < 1024: return f"{b} B"
            if b < 1048576: return f"{b//1024} KB"
            return f"{b/1048576:.1f} MB"

        rows = ""
        for p in pages:
            esc_id = html_mod.escape(p.get("id", ""))
            esc_title = html_mod.escape(p.get("title", "")[:70])
            esc_url = html_mod.escape(p.get("url", ""))
            esc_preview = html_mod.escape(p.get("preview", "")[:120])
            ago = _ago(p.get("saved", 0))
            size = _size(p.get("size", 0))
            rows += (
                f'<div class="entry" style="flex-direction:column;align-items:stretch;gap:4px;">'
                f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<a href="shroud://savedview?id={esc_id}" class="entry-link" style="flex:1;min-width:0;">'
                f'<div class="entry-title">{esc_title}</div>'
                f'<div class="entry-url">{esc_url}</div></a>'
                f'<span style="font-size:10px;color:{TEXT_FAINT};flex-shrink:0;">{ago} &middot; {size}</span>'
                f'<button class="act-btn visit" onclick="window.location.href=\'{esc_url}\'">Visit</button>'
                f'<button class="act-btn danger" onclick="pageAct(\'del_saved\',\'{esc_id}\')">Delete</button>'
                f'</div>'
                f'<div style="font-size:11px;color:{TEXT_FAINT};overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap;">{esc_preview}</div>'
                f'</div>'
            )

        if not pages:
            rows = (
                '<div class="empty">No saved pages yet. '
                'Press Ctrl+Shift+D to save any page for offline reading.</div>'
            )

        content = f"""
    <div class="section-desc">{len(pages)} page{'s' if len(pages) != 1 else ''} saved</div>
    <div class="card">{rows}</div>"""

        return self._wrap("Saved Pages", "saved", content, extra_js="""
    function pageAct(action, arg) {
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action:action,arg:arg}));
      setTimeout(function(){ location.reload(); }, 200);
    }""")

    def _page_saved_view(self, url):
        """Render a saved page snapshot for offline reading."""
        from PyQt6.QtCore import QUrlQuery
        query = QUrlQuery(url)
        page_id = query.queryItemValue("id")
        html_content = storage.get_saved_page_html(page_id)
        if not html_content:
            return self._page_error("shroud://savedview?id=" + page_id)
        # Find metadata
        pages = storage.load_saved_pages()
        meta = next((p for p in pages if p.get("id") == page_id), {})
        orig_url = meta.get("url", "")
        title = meta.get("title", "Saved Page")

        esc_title = html_mod.escape(title)
        esc_url = html_mod.escape(orig_url)

        # Inject a toolbar into the saved page
        toolbar = f"""<div style="position:fixed;top:0;left:0;right:0;z-index:2147483647;
            background:{BG_MID};border-bottom:1px solid {BORDER};
            padding:6px 16px;display:flex;align-items:center;gap:12px;
            font-family:-apple-system,Cantarell,sans-serif;font-size:12px;">
            <span style="color:{ACCENT};font-weight:600;">SAVED</span>
            <span style="color:{TEXT_DIM};flex:1;overflow:hidden;text-overflow:ellipsis;
                white-space:nowrap;">{esc_title} &mdash; {esc_url}</span>
            <a href="{esc_url}" style="color:{GREEN};text-decoration:none;font-size:11px;">Visit Original</a>
            <a href="shroud://saved" style="color:{ACCENT};text-decoration:none;font-size:11px;">Back to List</a>
        </div>
        <div style="height:36px;"></div>"""

        # Inject toolbar right after <body> tag
        import re
        modified = re.sub(
            r'(<body[^>]*>)', r'\1' + toolbar,
            html_content, count=1, flags=re.IGNORECASE,
        )
        if modified == html_content:
            # No <body> tag found — prepend
            modified = toolbar + html_content

        return modified

    def _page_apps(self):
        """Generate the shroud://apps installed PWA management page."""
        import time as _time
        apps = storage.load_installed_apps()

        rows = ""
        for app in apps:
            esc_name = html_mod.escape(app.get("name", "App"))
            esc_url = html_mod.escape(app.get("start_url", ""))
            icon = app.get("icon_path", "")
            ago = ""
            ts = app.get("installed", 0)
            if ts:
                d = _time.time() - ts
                if d < 3600:
                    ago = f"{int(d/60)}m ago"
                elif d < 86400:
                    ago = f"{int(d/3600)}h ago"
                else:
                    ago = f"{int(d/86400)}d ago"

            icon_html = ""
            if icon and os.path.exists(icon):
                icon_html = (
                    f'<img src="file://{html_mod.escape(icon)}" '
                    f'style="width:32px;height:32px;border-radius:6px;object-fit:cover;" '
                    f'onerror="this.style.display=\'none\'">'
                )
            else:
                icon_html = (
                    f'<div style="width:32px;height:32px;border-radius:6px;'
                    f'background:{BG_ACTIVE};display:flex;align-items:center;'
                    f'justify-content:center;font-size:16px;color:{TEXT_FAINT};">'
                    f'\u2B1A</div>'
                )

            rows += (
                f'<div class="entry" style="gap:14px;">'
                f'{icon_html}'
                f'<div style="flex:1;min-width:0;">'
                f'<div class="entry-title">{esc_name}</div>'
                f'<div class="entry-url">{esc_url}</div></div>'
                f'<span style="font-size:10px;color:{TEXT_FAINT};flex-shrink:0;">'
                f'{ago}</span>'
                f'<button class="act-btn visit" '
                f'onclick="pageAct(\'launch_app\',\'{esc_url}\')">Launch</button>'
                f'<button class="act-btn danger" '
                f'onclick="pageAct(\'uninstall_app\',\'{esc_url}\')">Uninstall</button>'
                f'</div>'
            )

        if not apps:
            rows = (
                '<div class="empty">No apps installed yet. '
                'Visit a PWA-enabled site and right-click to install it.</div>'
            )

        content = f"""
    <div class="section-desc">{len(apps)} app{'s' if len(apps) != 1 else ''} installed</div>
    <div class="card">{rows}</div>"""

        return self._wrap("Installed Apps", "apps", content, extra_js="""
    function pageAct(action, arg) {
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action:action,arg:arg}));
      setTimeout(function(){ location.reload(); }, 300);
    }""")

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
            for feat, entry in sorted(features.items()):
                # Support both old format (bare string) and new format (dict)
                if isinstance(entry, dict):
                    decision = entry.get("decision", "allow")
                else:
                    decision = entry
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

    def _page_permissions(self):
        """Generate the shroud://permissions audit-log page."""
        from . import permission_ledger
        import time as _time

        entries = permission_ledger.get_usage(limit=500)
        anomalies = permission_ledger.get_anomalies(threshold=10, hours=1)

        # Build anomaly badges
        anomaly_set: set[tuple[str, str]] = set()
        for a in anomalies:
            anomaly_set.add((a["host"], a["feature"]))

        # Stat cards
        total_events = len(entries)
        unique_hosts = len({e["host"] for e in entries})
        grants = sum(1 for e in entries if e["action"] == "grant")
        denies = sum(1 for e in entries if e["action"] == "deny")

        # Group entries by host
        by_host: dict[str, list[dict]] = {}
        for e in entries:
            by_host.setdefault(e["host"], []).append(e)

        # Build host sections
        host_cards = ""
        for host in sorted(by_host.keys()):
            host_entries = by_host[host]
            esc_host = html_mod.escape(host)
            rows = ""
            for e in host_entries:
                ts = _time.strftime("%Y-%m-%d %H:%M:%S",
                                    _time.localtime(e["timestamp"]))
                esc_feat = html_mod.escape(e["feature"])
                action = html_mod.escape(e["action"])
                color = "green" if action == "grant" else "red"
                anomaly_badge = ""
                if (e["host"], e["feature"]) in anomaly_set:
                    anomaly_badge = (
                        f' <span class="anomaly-badge">high frequency</span>'
                    )
                rows += (
                    f'<tr>'
                    f'<td class="ts">{ts}</td>'
                    f'<td class="perm-feat">{esc_feat}{anomaly_badge}</td>'
                    f'<td class="dot-cell"><span class="dot {color}"></span></td>'
                    f'<td class="perm-dec">{action}</td>'
                    f'</tr>'
                )

            host_cards += f"""
        <div class="site-card host-group" data-host="{esc_host}">
          <div class="site-header">
            <span class="site-name">{esc_host}</span>
            <span class="site-stats">{len(host_entries)} events</span>
          </div>
          <table class="req-table">{rows}</table>
        </div>"""

        if not host_cards:
            host_cards = (
                '<div class="empty">No permission events recorded yet. '
                'Grant or deny site permissions to see them here.</div>'
            )

        content = f"""
    <div class="stat-row" style="grid-template-columns: repeat(4, 1fr);">
      <div class="stat-card">
        <div class="stat-num events">{total_events}</div>
        <div class="stat-label">Total Events</div>
      </div>
      <div class="stat-card">
        <div class="stat-num hosts">{unique_hosts}</div>
        <div class="stat-label">Sites</div>
      </div>
      <div class="stat-card">
        <div class="stat-num granted">{grants}</div>
        <div class="stat-label">Granted</div>
      </div>
      <div class="stat-card">
        <div class="stat-num denied">{denies}</div>
        <div class="stat-label">Denied</div>
      </div>
    </div>

    <div class="toolbar">
      <input type="text" id="hostFilter" placeholder="Filter by host..."
             oninput="filterHosts(this.value)">
      <button class="act-btn export-btn" onclick="permAct('export')">Export CSV</button>
    </div>

    <div class="section" id="hostList">
      <h2>Permission Events by Host</h2>
      {host_cards}
    </div>

    <div class="reload-banner" id="reloadBanner">
      Done. <button onclick="location.reload()">Refresh</button>
    </div>"""

        extra_css = f"""
  .stat-num.events {{ color: {ACCENT}; }}
  .stat-num.hosts {{ color: {YELLOW}; }}
  .stat-num.granted {{ color: {GREEN}; }}
  .stat-num.denied {{ color: {RED}; }}
  .section h2 {{
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 3px; color: {TEXT_FAINT};
    font-weight: 600; margin-bottom: 10px; padding-left: 4px;
  }}
  .toolbar {{
    display: flex; gap: 10px; align-items: center;
    margin-bottom: 16px;
  }}
  .toolbar input {{
    flex: 1; padding: 8px 14px; font-size: 13px;
    background: {BG_CARD}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    outline: none; font-family: inherit;
  }}
  .toolbar input:focus {{
    border-color: {ACCENT};
  }}
  .export-btn {{
    white-space: nowrap;
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
  .req-table td.ts {{
    color: {TEXT_FAINT};
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px; width: 160px;
  }}
  .req-table td.perm-feat {{
    color: {TEXT_DIM}; font-family: monospace; font-size: 11px;
  }}
  .req-table td.perm-dec {{
    text-align: right; font-size: 11px;
  }}
  .req-table tr + tr td {{ border-top: 1px solid {BORDER}; }}
  .anomaly-badge {{
    display: inline-block;
    padding: 1px 6px; border-radius: 4px;
    font-size: 9px; font-weight: 600;
    background: rgba(229, 115, 115, 0.15);
    color: {RED}; border: 1px solid rgba(229, 115, 115, 0.3);
    margin-left: 6px; vertical-align: middle;
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
    function filterHosts(text) {
      var cards = document.querySelectorAll('.host-group');
      var t = text.toLowerCase();
      for (var i = 0; i < cards.length; i++) {
        var host = cards[i].getAttribute('data-host') || '';
        cards[i].style.display = (!t || host.toLowerCase().indexOf(t) !== -1)
          ? '' : 'none';
      }
    }
    function permAct(action) {
      console.log('__SHROUD_PERM_LEDGER__:' + JSON.stringify({
        action: action
      }));
      document.getElementById('reloadBanner').style.display = 'block';
    }"""

        return self._wrap("Permission Ledger", "permissions", content,
                          extra_css=extra_css, extra_js=extra_js)

    def _page_background(self):
        """Generate the shroud://background activity dashboard."""
        import time as _time

        mw = self.parent()
        bg = getattr(mw, "_bg_activity", None)

        workers = bg.get_all_workers() if bg else {}
        subs = bg.get_all_subscriptions() if bg else {}

        num_workers = len(workers)
        num_paused = sum(1 for w in workers.values() if w.get("paused"))
        num_active = num_workers - num_paused
        num_subs = len(subs)

        def _ago(ts):
            if not ts:
                return "unknown"
            d = _time.time() - ts
            if d < 60:
                return f"{int(d)}s ago"
            if d < 3600:
                return f"{int(d / 60)}m ago"
            if d < 86400:
                return f"{int(d / 3600)}h ago"
            return f"{int(d / 86400)}d ago"

        # Summary stats
        content = f"""
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-num">{num_workers}</div>
        <div class="stat-label">Service Workers</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{num_active}</div>
        <div class="stat-label">Active</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{num_paused}</div>
        <div class="stat-label">Paused</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{num_subs}</div>
        <div class="stat-label">Push Subscriptions</div>
      </div>
    </div>"""

        # Service workers section
        if workers:
            worker_rows = ""
            for host, info in sorted(workers.items()):
                esc_host = html_mod.escape(host)
                esc_scope = html_mod.escape(info.get("scope", "/"))
                paused = info.get("paused", False)
                status_dot = "yellow" if paused else "green"
                status_text = "Paused" if paused else "Active"
                reg_ago = _ago(info.get("registered_at"))
                toggle_label = "Resume" if paused else "Pause"
                toggle_action = "resume_worker" if paused else "pause_worker"

                worker_rows += (
                    f'<div class="entry">'
                    f'<span class="dot {status_dot}"></span>'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div class="entry-title">{esc_host}</div>'
                    f'<div class="entry-url">Scope: {esc_scope}</div>'
                    f'</div>'
                    f'<span class="entry-date">Registered {reg_ago}</span>'
                    f'<span style="font-size:11px;color:{TEXT_DIM};">{status_text}</span>'
                    f'<button class="act-btn" '
                    f'onclick="bgAct(\'{toggle_action}\',\'{esc_host}\')">{toggle_label}</button>'
                    f'<button class="act-btn danger" '
                    f'onclick="bgAct(\'unregister_worker\',\'{esc_host}\')">Unregister</button>'
                    f'</div>'
                )
        else:
            worker_rows = (
                '<div class="empty">No service workers detected. '
                'Service workers will appear here when sites register them.</div>'
            )

        content += f"""
    <div class="section">
      <div class="section-title">Service Workers</div>
      <div class="section-desc">{num_workers} registered worker{'s' if num_workers != 1 else ''}</div>
      <div class="card">{worker_rows}</div>
    </div>"""

        # Push subscriptions section
        if subs:
            sub_rows = ""
            for host, info in sorted(subs.items()):
                esc_host = html_mod.escape(host)
                endpoint = info.get("endpoint", "")
                # Truncate long endpoints for display
                if len(endpoint) > 80:
                    display_endpoint = html_mod.escape(endpoint[:77]) + "..."
                else:
                    display_endpoint = html_mod.escape(endpoint)
                sub_ago = _ago(info.get("subscribed_at"))

                sub_rows += (
                    f'<div class="entry">'
                    f'<span class="dot green"></span>'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div class="entry-title">{esc_host}</div>'
                    f'<div class="entry-url">{display_endpoint}</div>'
                    f'</div>'
                    f'<span class="entry-date">Subscribed {sub_ago}</span>'
                    f'<button class="act-btn danger" '
                    f'onclick="bgAct(\'revoke_push\',\'{esc_host}\')">Revoke</button>'
                    f'</div>'
                )
        else:
            sub_rows = (
                '<div class="empty">No push subscriptions detected. '
                'Subscriptions will appear here when sites request push notifications.</div>'
            )

        content += f"""
    <div class="section">
      <div class="section-title">Push Subscriptions</div>
      <div class="section-desc">{num_subs} active subscription{'s' if num_subs != 1 else ''}</div>
      <div class="card">{sub_rows}</div>
    </div>"""

        extra_js = """
    function bgAct(action, host) {
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action:action,arg:host}));
      setTimeout(function(){ location.reload(); }, 300);
    }"""

        return self._wrap("Background Activity", "background", content,
                          extra_js=extra_js)

    def _page_captures(self):
        """Generate the shroud://captures page showing WARC capture status."""
        import time as _time

        # Access the WarcCapture instance from the main window
        mw = self.parent()
        warc = getattr(mw, '_warc_capture', None)

        is_active = warc.is_active if warc else False
        record_count = warc.record_count if warc else 0
        page_count = warc.page_count if warc else 0
        captured_urls = warc.captured_urls if warc else []

        status_color = GREEN if is_active else TEXT_FAINT
        status_text = "Recording" if is_active else "Inactive"
        status_icon = "\u23f9" if is_active else "\u23fa"

        # Citation info
        citation = warc.get_citation() if warc and record_count > 0 else None
        citation_html = ""
        if citation:
            esc_url = html_mod.escape(citation.get("url", ""))
            esc_sha = html_mod.escape(citation.get("archive_sha256", ""))
            esc_time = html_mod.escape(citation.get("captured_at", ""))
            citation_html = f"""
    <div class="section">
      <div class="section-title">Citation</div>
      <div class="card card-padded">
        <div class="row">
          <span class="row-label">Start URL</span>
          <code style="font-size:11px;color:{ACCENT};word-break:break-all;">{esc_url}</code>
        </div>
        <div class="row">
          <span class="row-label">Captured At</span>
          <span style="font-size:12px;color:{TEXT_DIM};">{esc_time}</span>
        </div>
        <div class="row">
          <span class="row-label">Archive SHA-256</span>
          <code style="font-size:10px;color:{TEXT_DIM};word-break:break-all;">{esc_sha}</code>
        </div>
        <div class="row">
          <span class="row-label">Pages</span>
          <span style="font-size:12px;color:{TEXT_DIM};">{citation.get("page_count", 0)}</span>
        </div>
      </div>
    </div>"""

        # Captured URLs list
        url_rows = ""
        for entry in captured_urls:
            esc_title = html_mod.escape(entry.get("title", "")[:70])
            esc_url = html_mod.escape(entry.get("url", ""))
            esc_ts = html_mod.escape(entry.get("timestamp", ""))
            url_rows += (
                f'<div class="entry">'
                f'<a href="{esc_url}" class="entry-link" style="flex:1;min-width:0;">'
                f'<div class="entry-title">{esc_title or esc_url}</div>'
                f'<div class="entry-url">{esc_url}</div></a>'
                f'<span class="entry-date">{esc_ts}</span>'
                f'</div>'
            )
        if not captured_urls:
            url_rows = (
                '<div class="empty">No pages captured yet. '
                'Start a capture and browse to record pages.</div>'
            )

        # Action buttons
        action_btns = ""
        if record_count > 0:
            action_btns = f"""
    <div style="display:flex;gap:10px;flex-wrap:wrap;">
      <button class="btn btn-primary" onclick="pageAct('save_wacz','')">Save as WACZ</button>
      <button class="btn btn-secondary" onclick="pageAct('save_warc','')">Save as WARC</button>
      <button class="btn btn-secondary" style="border-color:{RED};color:{RED};"
              onclick="if(confirm('Clear all capture data?')){{pageAct('clear_capture','');setTimeout(function(){{location.reload();}},300);}}">
        Clear Capture</button>
    </div>"""

        content = f"""
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-num" style="color:{status_color};">{status_icon}</div>
        <div class="stat-label">{status_text}</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{record_count}</div>
        <div class="stat-label">Records</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{page_count}</div>
        <div class="stat-label">Pages</div>
      </div>
    </div>

    {action_btns}

    <div class="section" style="margin-top:24px;">
      <div class="section-title">Captured Pages</div>
      <div class="card">{url_rows}</div>
    </div>

    {citation_html}

    <div class="section">
      <div class="section-title">About WARC/WACZ</div>
      <div class="section-desc">
        WARC (Web ARChive) is an ISO 28500 standard for recording web content.
        WACZ (Web Archive Collection Zipped) bundles WARC data with metadata
        for easy sharing and replay. Start a capture session using the toolbar
        button or the Tools menu, then browse normally. Every page you visit
        will be recorded. Stop the capture when done and save your archive.
      </div>
    </div>"""

        extra_js = """
    function pageAct(action, arg) {
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action:action,arg:arg}));
      setTimeout(function(){ location.reload(); }, 300);
    }"""

        return self._wrap("Captures", "captures", content, extra_js=extra_js)

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

    def _page_extensions(self):
        """Generate the shroud://extensions management page."""
        from .extensions import ExtensionManager

        mgr = ExtensionManager()
        extensions = mgr.get_extensions()

        ext_dir = str(mgr._extensions_dir)
        esc_dir = html_mod.escape(ext_dir)

        cards = ""
        for ext in extensions:
            esc_name = html_mod.escape(ext.name)
            esc_ver = html_mod.escape(ext.version)
            esc_desc = html_mod.escape(ext.description) if ext.description else "<em>No description</em>"
            dir_name = html_mod.escape(ext.path.name)
            enabled_cls = "enabled" if ext.enabled else "disabled"
            toggle_action = "disable_ext" if ext.enabled else "enable_ext"
            toggle_label = "Disable" if ext.enabled else "Enable"
            status_text = "Enabled" if ext.enabled else "Disabled"
            status_color = "green" if ext.enabled else "dim"

            # Summarise content scripts
            scripts_info = ""
            for i, cs in enumerate(ext.content_scripts):
                patterns = ", ".join(cs.matches[:3])
                if len(cs.matches) > 3:
                    patterns += f" (+{len(cs.matches) - 3} more)"
                js_count = len(cs.js)
                css_count = len(cs.css)
                scripts_info += (
                    f'<div class="cs-info">'
                    f'<span class="cs-matches">{html_mod.escape(patterns)}</span>'
                    f' &mdash; {js_count} JS, {css_count} CSS'
                    f' @ {html_mod.escape(cs.run_at)}'
                    f'</div>'
                )

            cards += f"""
    <div class="ext-card {enabled_cls}">
      <div class="ext-header">
        <div class="ext-title">{esc_name}
          <span class="ext-version">v{esc_ver}</span>
        </div>
        <span class="ext-status {status_color}">{status_text}</span>
      </div>
      <div class="ext-desc">{esc_desc}</div>
      {scripts_info if scripts_info else ''}
      <div class="ext-path">
        <code>{dir_name}/</code>
      </div>
      <div class="ext-actions">
        <button class="btn btn-sm"
          onclick="extAct('{toggle_action}','{dir_name}')">{toggle_label}</button>
      </div>
    </div>"""

        if not extensions:
            cards = (
                '<div class="empty-state">'
                '<div class="empty-icon">\u29C9</div>'
                '<div class="empty-title">No Extensions Installed</div>'
                '<div class="empty-desc">'
                'Create a directory inside the extensions folder with a '
                '<code>manifest.json</code> file to get started.'
                '</div>'
                '</div>'
            )

        content = f"""
    <div class="section-desc">
      Content script extensions inject JavaScript and CSS into web pages.
      Each extension is a folder with a <code>manifest.json</code> inside the extensions directory.
    </div>

    <div class="info-bar">
      <div class="info-label">Extensions directory</div>
      <code class="info-path">{esc_dir}</code>
    </div>

    <div class="toolbar">
      <button class="btn btn-primary" onclick="extAct('reload_extensions','')">
        Reload Extensions</button>
      <span class="ext-count">{len(extensions)} extension{"s" if len(extensions) != 1 else ""}</span>
    </div>

    <div class="ext-list">{cards}</div>

    <div class="section" style="margin-top:36px;">
      <div class="section-title">How to Install Extensions</div>
      <div class="instructions card card-padded">
        <ol>
          <li>Create a directory inside <code>{esc_dir}/</code></li>
          <li>Add a <code>manifest.json</code> file with this format:
<pre>{{
  "name": "My Extension",
  "version": "1.0",
  "description": "What it does",
  "content_scripts": [{{
    "matches": ["*://*.example.com/*"],
    "js": ["content.js"],
    "css": ["style.css"],
    "run_at": "document_idle"
  }}]
}}</pre>
          </li>
          <li>Add your <code>.js</code> and <code>.css</code> files in the same directory</li>
          <li>Click <strong>Reload Extensions</strong> above</li>
        </ol>
        <div class="instructions-note">
          <strong>Match patterns:</strong> Use <code>&lt;all_urls&gt;</code> to match every page,
          or <code>*://*.example.com/*</code> for specific sites.
          <code>run_at</code> can be <code>document_start</code>, <code>document_end</code>,
          or <code>document_idle</code> (default).
        </div>
      </div>
    </div>"""

        extra_css = f"""
  .section-desc {{
    color: {TEXT_DIM}; font-size: 13px; margin-bottom: 20px; line-height: 1.6;
  }}
  .section-desc code {{
    background: {BG_CARD}; padding: 2px 6px; border-radius: 4px;
    font-size: 12px; color: {ACCENT};
  }}
  .info-bar {{
    display: flex; align-items: center; gap: 12px;
    padding: 12px 18px; margin-bottom: 20px;
    background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px;
  }}
  .info-label {{
    font-size: 11px; font-weight: 600; color: {TEXT_FAINT};
    text-transform: uppercase; letter-spacing: 1px; flex-shrink: 0;
  }}
  .info-path {{
    font-size: 12px; color: {TEXT_DIM};
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    word-break: break-all;
  }}
  .toolbar {{
    display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
  }}
  .ext-count {{
    font-size: 12px; color: {TEXT_FAINT};
  }}
  .ext-list {{ display: flex; flex-direction: column; gap: 12px; }}
  .ext-card {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 12px; padding: 18px 22px;
    transition: border-color 0.2s;
  }}
  .ext-card:hover {{ border-color: {ACCENT}33; }}
  .ext-card.disabled {{ opacity: 0.6; }}
  .ext-header {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 6px;
  }}
  .ext-title {{
    font-size: 15px; font-weight: 600; color: {TEXT};
  }}
  .ext-version {{
    font-size: 11px; font-weight: 400; color: {TEXT_FAINT}; margin-left: 8px;
  }}
  .ext-status {{
    font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
    font-weight: 600; padding: 3px 8px; border-radius: 6px;
  }}
  .ext-status.green {{ color: {GREEN}; background: {GREEN}15; }}
  .ext-status.dim {{ color: {TEXT_FAINT}; background: {BG_HOVER}; }}
  .ext-desc {{
    font-size: 13px; color: {TEXT_DIM}; margin-bottom: 8px; line-height: 1.5;
  }}
  .ext-desc em {{ color: {TEXT_FAINT}; }}
  .cs-info {{
    font-size: 11px; color: {TEXT_FAINT}; margin-bottom: 4px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
  }}
  .cs-matches {{ color: {ACCENT}; }}
  .ext-path {{
    font-size: 11px; color: {TEXT_FAINT}; margin-top: 6px;
  }}
  .ext-path code {{
    background: {BG_DARK}; padding: 2px 6px; border-radius: 4px;
    font-size: 11px;
  }}
  .ext-actions {{
    display: flex; gap: 8px; justify-content: flex-end; margin-top: 10px;
  }}
  .btn {{
    padding: 8px 16px; font-size: 13px; font-weight: 500;
    border: 1px solid {BORDER}; border-radius: 8px;
    cursor: pointer; background: {BG_DARK}; color: {TEXT};
    transition: all 0.15s;
  }}
  .btn:hover {{ background: {BG_HOVER}; }}
  .btn-sm {{ padding: 6px 12px; font-size: 12px; }}
  .btn-primary {{
    background: {ACCENT}; color: {BG_DARK};
    border-color: {ACCENT}; font-weight: 600;
  }}
  .btn-primary:hover {{ background: {ACCENT_HOVER}; }}
  .empty-state {{
    text-align: center; padding: 48px 24px;
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 12px;
  }}
  .empty-icon {{ font-size: 48px; color: {TEXT_FAINT}; margin-bottom: 16px; }}
  .empty-title {{ font-size: 16px; font-weight: 600; color: {TEXT}; margin-bottom: 8px; }}
  .empty-desc {{
    font-size: 13px; color: {TEXT_DIM}; line-height: 1.6;
  }}
  .empty-desc code {{
    background: {BG_DARK}; padding: 2px 6px; border-radius: 4px;
    font-size: 12px; color: {ACCENT};
  }}
  .instructions {{
    font-size: 13px; color: {TEXT_DIM}; line-height: 1.8;
    padding: 20px 24px !important;
  }}
  .instructions ol {{ padding-left: 20px; }}
  .instructions li {{ margin-bottom: 12px; }}
  .instructions code {{
    background: {BG_DARK}; padding: 2px 6px; border-radius: 4px;
    font-size: 12px; color: {ACCENT};
  }}
  .instructions pre {{
    background: {BG_DARK}; padding: 14px 18px; border-radius: 8px;
    font-size: 12px; color: {TEXT}; margin: 8px 0;
    overflow-x: auto; white-space: pre;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    border: 1px solid {BORDER};
  }}
  .instructions-note {{
    margin-top: 16px; padding: 12px 16px;
    background: {BG_DARK}; border-radius: 8px;
    font-size: 12px; color: {TEXT_FAINT}; line-height: 1.6;
    border: 1px solid {BORDER};
  }}
  .instructions-note code {{
    background: {BG_CARD};
  }}"""

        extra_js = """
    function extAct(action, arg) {
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action: action, arg: arg}));
      setTimeout(function() { location.reload(); }, 300);
    }"""

        return self._wrap("Extensions", "extensions", content,
                          extra_css=extra_css, extra_js=extra_js)

    def _page_profiles(self):
        """Generate the shroud://profiles container management page."""
        from .profiles import ProfileManager, _DEFAULT_PROFILES

        profiles_data = storage._load_json("profiles.json", None)
        if profiles_data is None:
            profiles_data = _DEFAULT_PROFILES

        # ── build profile cards ──
        cards = ""
        for p in profiles_data:
            name = p.get("name", "")
            color = p.get("color", "#6366f1")
            auto_assign = p.get("auto_assign", [])
            esc_name = html_mod.escape(name)
            esc_color = html_mod.escape(color)
            domains_str = ", ".join(auto_assign) if auto_assign else ""
            esc_domains = html_mod.escape(domains_str)
            is_default = name == "Default"

            delete_btn = ""
            if not is_default:
                delete_btn = (
                    f'<button class="btn btn-danger" '
                    f"onclick=\"profileAct('remove_profile','{esc_name}')\">"
                    f'Delete</button>'
                )

            cards += f"""
    <div class="profile-card">
      <div class="profile-header">
        <span class="color-swatch" style="background:{esc_color}"></span>
        <span class="profile-name">{esc_name}</span>
        {f'<span class="badge">default</span>' if is_default else ''}
      </div>
      <div class="profile-body">
        <label class="field-label">Color</label>
        <div class="color-row">
          <input type="color" value="{esc_color}" class="color-input"
            id="color-{esc_name}"
            onchange="profileAct('update_profile','{esc_name}',
              JSON.stringify({{color:this.value}}))">
          <span class="color-hex">{esc_color}</span>
        </div>
        <label class="field-label">Auto-assign domains
          <span class="hint">(comma-separated, e.g. github.com, gitlab.com)</span>
        </label>
        <div class="domain-row">
          <input type="text" class="domain-input" value="{esc_domains}"
            id="domains-{esc_name}" placeholder="No auto-assign rules">
          <button class="btn btn-sm"
            onclick="saveDomains('{esc_name}')">Save</button>
        </div>
      </div>
      <div class="profile-actions">
        {delete_btn}
      </div>
    </div>"""

        content = f"""
    <div class="section-desc">
      Container profiles isolate cookies, storage, and cache.
      Each profile uses a separate browser engine profile.
    </div>

    <div class="add-form">
      <input type="text" id="new-name" class="add-input"
        placeholder="New profile name">
      <input type="color" id="new-color" value="#6366f1" class="color-input">
      <button class="btn btn-primary" onclick="addProfile()">
        Add Profile</button>
    </div>

    <div class="profile-list">{cards}</div>"""

        extra_css = f"""
  .section-desc {{
    color: {TEXT_DIM}; font-size: 13px; margin-bottom: 24px;
    line-height: 1.6;
  }}
  .add-form {{
    display: flex; gap: 10px; align-items: center;
    margin-bottom: 32px; padding: 16px 20px;
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 12px;
  }}
  .add-input {{
    flex: 1; padding: 10px 14px; font-size: 14px;
    background: {BG_DARK}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    outline: none;
  }}
  .add-input:focus {{ border-color: {ACCENT}; }}
  .color-input {{
    width: 40px; height: 36px; border: none;
    border-radius: 8px; cursor: pointer;
    background: transparent; padding: 0;
  }}
  .profile-list {{ display: flex; flex-direction: column; gap: 16px; }}
  .profile-card {{
    background: {BG_CARD}; border: 1px solid {BORDER};
    border-radius: 12px; padding: 20px 24px;
    transition: border-color 0.2s;
  }}
  .profile-card:hover {{ border-color: {ACCENT}33; }}
  .profile-header {{
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 16px;
  }}
  .color-swatch {{
    width: 16px; height: 16px; border-radius: 50%;
    flex-shrink: 0;
  }}
  .profile-name {{
    font-size: 16px; font-weight: 600; color: {TEXT};
  }}
  .badge {{
    font-size: 10px; text-transform: uppercase;
    letter-spacing: 1px; color: {ACCENT};
    background: {ACCENT}15; padding: 3px 8px;
    border-radius: 6px; font-weight: 600;
  }}
  .profile-body {{ margin-bottom: 12px; }}
  .field-label {{
    display: block; font-size: 11px; font-weight: 600;
    color: {TEXT_FAINT}; text-transform: uppercase;
    letter-spacing: 1px; margin-bottom: 6px; margin-top: 12px;
  }}
  .field-label .hint {{
    font-weight: 400; text-transform: none;
    letter-spacing: 0; color: {TEXT_FAINT};
    font-size: 11px;
  }}
  .color-row {{
    display: flex; align-items: center; gap: 10px;
  }}
  .color-hex {{
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px; color: {TEXT_DIM};
  }}
  .domain-row {{
    display: flex; gap: 8px; align-items: center;
  }}
  .domain-input {{
    flex: 1; padding: 8px 12px; font-size: 13px;
    background: {BG_DARK}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    outline: none;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
  }}
  .domain-input:focus {{ border-color: {ACCENT}; }}
  .profile-actions {{
    display: flex; gap: 8px; justify-content: flex-end;
  }}
  .btn {{
    padding: 8px 16px; font-size: 13px; font-weight: 500;
    border: 1px solid {BORDER}; border-radius: 8px;
    cursor: pointer; background: {BG_DARK}; color: {TEXT};
    transition: all 0.15s;
  }}
  .btn:hover {{ background: {BG_HOVER}; }}
  .btn-sm {{ padding: 6px 12px; font-size: 12px; }}
  .btn-primary {{
    background: {ACCENT}; color: {BG_DARK};
    border-color: {ACCENT}; font-weight: 600;
  }}
  .btn-primary:hover {{ background: {ACCENT_HOVER}; }}
  .btn-danger {{
    color: {RED}; border-color: {RED}44;
  }}
  .btn-danger:hover {{
    background: {RED}22; border-color: {RED};
  }}"""

        extra_js = """
    function profileAct(action, arg, extra) {
      var payload = {action: action, arg: arg || ''};
      if (extra) {
        try { Object.assign(payload, JSON.parse(extra)); } catch(e) {}
      }
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify(payload));
      setTimeout(function() { location.reload(); }, 250);
    }

    function addProfile() {
      var name = document.getElementById('new-name').value.trim();
      var color = document.getElementById('new-color').value;
      if (!name) { alert('Please enter a profile name.'); return; }
      profileAct('add_profile', name, JSON.stringify({color: color}));
    }

    function saveDomains(name) {
      var input = document.getElementById('domains-' + name);
      var domains = input.value.split(',').map(function(d) {
        return d.trim();
      }).filter(function(d) { return d.length > 0; });
      profileAct('update_profile', name,
        JSON.stringify({auto_assign: domains}));
    }"""

        return self._wrap("Profiles", "profiles", content,
                          extra_css=extra_css, extra_js=extra_js)

    def _page_sessions(self):
        """Generate the shroud://sessions named session management page."""
        import time as _time
        from . import session_manager

        sessions = session_manager.list_sessions()

        def _ago(ts):
            if not ts:
                return "never"
            d = _time.time() - ts
            if d < 60: return "just now"
            if d < 3600: return f"{int(d/60)}m ago"
            if d < 86400: return f"{int(d/3600)}h ago"
            return f"{int(d/86400)}d ago"

        rows = ""
        for s in sessions:
            esc_name = html_mod.escape(s["name"])
            ago = _ago(s["updated_at"])
            tab_count = s["tab_count"]
            rows += (
                f'<div class="entry" style="gap:10px;">'
                f'<div style="flex:1;min-width:0;">'
                f'<div class="entry-title">{esc_name}</div>'
                f'<div class="entry-url">{tab_count} tab{"s" if tab_count != 1 else ""}'
                f' &middot; updated {ago}</div></div>'
                f'<button class="act-btn visit" '
                f'onclick="pageAct(\'load_session\',\'{esc_name}\')">Load</button>'
                f'<button class="act-btn danger" '
                f'onclick="pageAct(\'delete_session\',\'{esc_name}\')">Delete</button>'
                f'</div>'
            )

        if not sessions:
            rows = (
                '<div class="empty">No saved sessions yet. '
                'Use the form above to save your current tabs as a named session.</div>'
            )

        content = f"""
    <div class="card" style="padding:16px;margin-bottom:16px;">
      <div style="font-size:14px;font-weight:600;margin-bottom:12px;">Save Current Session</div>
      <div style="display:flex;gap:8px;align-items:center;">
        <input id="session-name" type="text" placeholder="Session name\u2026"
          style="flex:1;padding:8px 12px;border-radius:8px;border:1px solid {BORDER};
          background:{BG_DARK};color:{TEXT};font-size:13px;font-family:inherit;"
          onkeydown="if(event.key==='Enter')saveSession()">
        <button class="act-btn visit" onclick="saveSession()"
          style="padding:8px 20px;">Save</button>
      </div>
    </div>
    <div class="section-desc">{len(sessions)} saved session{"s" if len(sessions) != 1 else ""}</div>
    <div class="card">{rows}</div>"""

        return self._wrap("Sessions", "sessions", content, extra_js="""
    function pageAct(action, arg) {
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action:action,arg:arg}));
      setTimeout(function(){ location.reload(); }, 300);
    }
    function saveSession() {
      var name = document.getElementById('session-name').value.trim();
      if (!name) return;
      console.log('__SHROUD_PAGE_ACT__:' + JSON.stringify({action:'save_session',arg:name}));
      setTimeout(function(){ location.reload(); }, 300);
    }""")

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
