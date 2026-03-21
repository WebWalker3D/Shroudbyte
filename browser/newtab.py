"""New-tab page HTML generator."""

import datetime

from . import storage
from .style import (
    ACCENT, ACCENT_HOVER, ACCENT_TEXT, BG_DARK, BG_CARD,
    BG_HOVER, BG_MID, TEXT, TEXT_DIM, TEXT_FAINT, BORDER,
)


def generate_new_tab_html():
    """Return HTML for a styled new-tab page with search and quick links."""
    bookmarks = storage.load_bookmarks()[:8]
    settings = storage.load_settings()
    search_url = settings.get("search_engine", "https://duckduckgo.com/?q={}")
    # Build the search action URL (everything before the {})
    search_action = search_url.split("?")[0] if "?" in search_url else search_url.replace("{}", "")
    search_param = ""
    if "?" in search_url:
        param_part = search_url.split("?")[1]
        if "={}" in param_part:
            search_param = param_part.split("={}")[0]

    # Time-based greeting
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        greeting = "Good morning"
    elif 12 <= hour < 17:
        greeting = "Good afternoon"
    elif 17 <= hour < 21:
        greeting = "Good evening"
    else:
        greeting = "Good night"

    bookmark_cards = ""
    for bm in bookmarks:
        title = bm["title"][:22] or bm["url"][:22]
        url = bm["url"]
        domain = url.split("//")[-1].split("/")[0] if "//" in url else url[:30]
        first_letter = title[0].upper() if title else domain[0].upper()
        bookmark_cards += f"""
            <a href="{url}" class="card">
                <div class="card-icon">{first_letter}</div>
                <div class="card-label">{title}</div>
                <div class="card-domain">{domain}</div>
            </a>"""

    if bookmarks:
        bookmarks_section = f"""
        <div class="quick-links">
            <div class="section-label">Quick Links</div>
            <div class="cards">{bookmark_cards}
            </div>
        </div>"""
    else:
        bookmarks_section = '<p class="empty">Bookmark pages to see them here</p>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: {BG_DARK};
    color: {TEXT};
    font-family: 'Cantarell', 'Noto Sans', system-ui, -apple-system, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    padding-top: 22vh;
    overflow-x: hidden;
  }}

  /* ── Atmospheric background ── */
  .bg-glow {{
    position: fixed;
    top: 22%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 900px;
    height: 600px;
    background: radial-gradient(
      ellipse,
      rgba(205, 141, 106, 0.04) 0%,
      transparent 65%
    );
    pointer-events: none;
    z-index: 0;
  }}

  .grain {{
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    pointer-events: none;
    opacity: 0.02;
    z-index: 1;
  }}

  .content {{
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
  }}

  /* ── Greeting ── */
  .greeting {{
    font-size: 13px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: {TEXT_FAINT};
    margin-bottom: 18px;
    font-weight: 500;
  }}

  /* ── Wordmark ── */
  .wordmark {{
    font-size: 48px;
    font-weight: 700;
    letter-spacing: 8px;
    text-transform: uppercase;
    text-indent: 8px;
    background: linear-gradient(
      135deg,
      {ACCENT_HOVER} 0%,
      {ACCENT} 35%,
      {ACCENT_TEXT} 65%,
      {ACCENT} 100%
    );
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 14px;
    user-select: none;
  }}

  .divider {{
    width: 50px;
    height: 1px;
    background: linear-gradient(90deg, transparent, {ACCENT}, transparent);
    margin-bottom: 40px;
    opacity: 0.5;
  }}

  /* ── Search ── */
  .search-container {{
    width: 560px;
    max-width: 88vw;
    margin-bottom: 52px;
  }}

  .search-container form {{
    position: relative;
    display: flex;
    width: 100%;
    align-items: center;
  }}

  .search-icon {{
    position: absolute;
    left: 18px;
    top: 50%;
    transform: translateY(-50%);
    color: {TEXT_FAINT};
    pointer-events: none;
    transition: color 0.25s ease;
  }}

  .search-container input {{
    width: 100%;
    padding: 15px 22px 15px 50px;
    font-size: 15px;
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 12px;
    outline: none;
    transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
    font-family: inherit;
  }}

  .search-container input:focus {{
    border-color: {ACCENT};
    box-shadow: 0 0 0 3px rgba(205, 141, 106, 0.08),
                0 8px 32px rgba(0, 0, 0, 0.2);
    background: {BG_MID};
  }}

  .search-container:focus-within .search-icon {{
    color: {ACCENT};
  }}

  .search-container input::placeholder {{
    color: {TEXT_FAINT};
    font-weight: 400;
  }}

  /* ── Quick Links ── */
  .quick-links {{
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
  }}

  .section-label {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 3px;
    color: {TEXT_FAINT};
    margin-bottom: 18px;
    font-weight: 600;
  }}

  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 10px;
    width: 560px;
    max-width: 88vw;
  }}

  .card {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px 10px 14px;
    background: rgba(28, 27, 36, 0.6);
    border: 1px solid rgba(40, 38, 51, 0.5);
    border-radius: 12px;
    text-decoration: none;
    color: {TEXT};
    transition: all 0.2s ease;
    cursor: pointer;
  }}

  .card:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
  }}

  .card-icon {{
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: linear-gradient(145deg, {ACCENT}, #a06b4c);
    color: {BG_DARK};
    font-size: 18px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 10px;
    user-select: none;
  }}

  .card-label {{
    font-size: 12px;
    font-weight: 500;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 110px;
  }}

  .card-domain {{
    font-size: 10px;
    color: {TEXT_FAINT};
    margin-top: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 110px;
  }}

  .empty {{
    color: {TEXT_FAINT};
    font-size: 13px;
    letter-spacing: 1px;
    text-align: center;
  }}

  /* ── Animations ── */
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}

  .greeting          {{ animation: fadeIn 0.5s ease 0.04s both; }}
  .wordmark           {{ animation: fadeIn 0.5s ease 0.10s both; }}
  .divider            {{ animation: fadeIn 0.5s ease 0.15s both; }}
  .search-container   {{ animation: fadeIn 0.5s ease 0.22s both; }}
  .quick-links, .empty {{ animation: fadeIn 0.5s ease 0.30s both; }}
</style>
</head>
<body>
  <div class="bg-glow"></div>
  <svg class="grain" width="100%" height="100%">
    <filter id="g">
      <feTurbulence baseFrequency="0.65" type="fractalNoise" numOctaves="3"/>
    </filter>
    <rect width="100%" height="100%" filter="url(#g)"/>
  </svg>

  <div class="content">
    <div class="greeting">{greeting}</div>
    <div class="wordmark">Shroudbyte</div>
    <div class="divider"></div>

    <div class="search-container">
      <form action="{search_action}" method="get">
        <input type="text" name="{search_param}" placeholder="Search the web\u2026" autofocus>
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <circle cx="11" cy="11" r="7"/>
          <path d="m20 20-4-4"/>
        </svg>
      </form>
    </div>

    {bookmarks_section}
  </div>
</body>
</html>"""
