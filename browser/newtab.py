"""New-tab page HTML generator."""

from . import storage
from .style import ACCENT, BG_DARK, BG_CARD, BG_HOVER, TEXT, TEXT_DIM, BORDER


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

    bookmark_cards = ""
    for bm in bookmarks:
        title = bm["title"][:20] or bm["url"][:20]
        # Extract domain for display
        url = bm["url"]
        domain = url.split("//")[-1].split("/")[0] if "//" in url else url[:30]
        first_letter = title[0].upper() if title else domain[0].upper()
        bookmark_cards += f"""
        <a href="{url}" class="card">
            <div class="card-icon">{first_letter}</div>
            <div class="card-label">{title}</div>
            <div class="card-domain">{domain}</div>
        </a>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {BG_DARK};
    color: {TEXT};
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    padding-top: 18vh;
  }}
  .logo {{
    font-size: 42px;
    font-weight: 700;
    letter-spacing: -1px;
    margin-bottom: 32px;
    background: linear-gradient(135deg, {ACCENT} 0%, #a78bfa 50%, #f472b6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    user-select: none;
  }}
  .search-box {{
    width: 560px;
    max-width: 90vw;
    margin-bottom: 48px;
  }}
  .search-box form {{
    display: flex;
    width: 100%;
  }}
  .search-box input {{
    width: 100%;
    padding: 14px 24px;
    font-size: 16px;
    background: {BG_CARD};
    color: {TEXT};
    border: 2px solid {BORDER};
    border-radius: 24px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    font-family: inherit;
  }}
  .search-box input:focus {{
    border-color: {ACCENT};
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
  }}
  .search-box input::placeholder {{
    color: {TEXT_DIM};
  }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 12px;
    width: 560px;
    max-width: 90vw;
  }}
  .card {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px 10px 14px;
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    text-decoration: none;
    color: {TEXT};
    transition: background 0.15s, border-color 0.15s, transform 0.15s;
    cursor: pointer;
  }}
  .card:hover {{
    background: {BG_HOVER};
    border-color: {ACCENT};
    transform: translateY(-2px);
  }}
  .card-icon {{
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, {ACCENT}, #818cf8);
    color: white;
    font-size: 20px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 10px;
    user-select: none;
  }}
  .card-label {{
    font-size: 13px;
    font-weight: 500;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 110px;
  }}
  .card-domain {{
    font-size: 11px;
    color: {TEXT_DIM};
    margin-top: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 110px;
  }}
  .empty {{
    color: {TEXT_DIM};
    font-size: 14px;
    text-align: center;
    margin-top: 8px;
  }}
</style>
</head>
<body>
  <div class="logo">Blade</div>
  <div class="search-box">
    <form action="{search_action}" method="get">
      <input type="text" name="{search_param}" placeholder="Search the web..." autofocus>
    </form>
  </div>
  {"<div class='cards'>" + bookmark_cards + "</div>" if bookmarks else "<p class='empty'>Bookmark pages to see them here</p>"}
</body>
</html>"""
