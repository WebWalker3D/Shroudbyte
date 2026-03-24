"""New-tab page HTML generator."""

import base64
import datetime
import hashlib
import html as html_mod
import os

from . import storage
from . import style as _style_mod


def _refresh_colors():
    """Pull current theme colours into module-level names."""
    g = globals()
    for _name in (
        "ACCENT", "ACCENT_HOVER", "ACCENT_TEXT", "BG_DARK", "BG_CARD",
        "BG_HOVER", "BG_MID", "TEXT", "TEXT_DIM", "TEXT_FAINT", "BORDER",
    ):
        g[_name] = getattr(_style_mod, _name)


_refresh_colors()

# ── Daily quotes ─────────────────────────────────────────────────
_QUOTES = [
    ("The best way to predict the future is to invent it.", "Alan Kay"),
    ("Simplicity is the ultimate sophistication.", "Leonardo da Vinci"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
    ("Stay hungry, stay foolish.", "Stewart Brand"),
    ("The computer was born to solve problems that did not exist before.", "Bill Gates"),
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("Any sufficiently advanced technology is indistinguishable from magic.", "Arthur C. Clarke"),
    ("Not all those who wander are lost.", "J.R.R. Tolkien"),
    ("The mind is everything. What you think you become.", "Buddha"),
    ("What we know is a drop, what we don't know is an ocean.", "Isaac Newton"),
    ("Do what you can, with what you have, where you are.", "Theodore Roosevelt"),
    ("In the middle of difficulty lies opportunity.", "Albert Einstein"),
    ("Be yourself; everyone else is already taken.", "Oscar Wilde"),
    ("The journey of a thousand miles begins with one step.", "Lao Tzu"),
    ("Imagination is more important than knowledge.", "Albert Einstein"),
    ("Life is what happens when you're busy making other plans.", "John Lennon"),
    ("The only limit to our realization of tomorrow is our doubts of today.", "Franklin D. Roosevelt"),
    ("We are what we repeatedly do. Excellence is not an act, but a habit.", "Aristotle"),
    ("I have not failed. I've just found 10,000 ways that won't work.", "Thomas Edison"),
    ("The unexamined life is not worth living.", "Socrates"),
    ("If you want to go fast, go alone. If you want to go far, go together.", "African Proverb"),
    ("Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away.", "Antoine de Saint-Exupery"),
    ("The best time to plant a tree was 20 years ago. The second best time is now.", "Chinese Proverb"),
    ("Everything you can imagine is real.", "Pablo Picasso"),
    ("One machine can do the work of fifty ordinary men. No machine can do the work of one extraordinary man.", "Elbert Hubbard"),
    ("The art of programming is the art of organizing complexity.", "Edsger W. Dijkstra"),
    ("Privacy is not something that I'm merely entitled to, it's an absolute prerequisite.", "Marlon Brando"),
    ("In a world of locked doors, the man with the key is king.", "Anonymous"),
    ("The advance of technology is based on making it fit in so that you don't really even notice it.", "Bill Gates"),
]


def _daily_quote():
    """Pick a quote that changes once per day, deterministically."""
    day_seed = datetime.date.today().toordinal()
    idx = int(hashlib.md5(str(day_seed).encode()).hexdigest(), 16) % len(_QUOTES)
    return _QUOTES[idx]


def _wallpaper_data_url(settings):
    """If a wallpaper file is configured and exists, return a data URL for it."""
    path = settings.get("wallpaper", "")
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            data = f.read()
        # Detect MIME from first bytes
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            mime = "image/png"
        elif data[:3] == b'\xff\xd8\xff':
            mime = "image/jpeg"
        elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            mime = "image/webp"
        elif data[:6] in (b'GIF87a', b'GIF89a'):
            mime = "image/gif"
        else:
            mime = "image/jpeg"
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


def _time_gradient():
    """Return a subtle ambient gradient colour based on time of day."""
    hour = datetime.datetime.now().hour
    # Morning: warm amber/gold
    if 5 <= hour < 9:
        return ("rgba(205, 160, 80, 0.06)", "rgba(180, 120, 60, 0.03)")
    # Midday: bright copper
    elif 9 <= hour < 14:
        return ("rgba(205, 141, 106, 0.05)", "rgba(200, 160, 120, 0.02)")
    # Afternoon: warm amber
    elif 14 <= hour < 17:
        return ("rgba(210, 150, 90, 0.06)", "rgba(190, 130, 70, 0.03)")
    # Evening: deep purple/copper
    elif 17 <= hour < 21:
        return ("rgba(160, 100, 140, 0.06)", "rgba(140, 80, 100, 0.03)")
    # Night: cool blue/indigo
    else:
        return ("rgba(80, 100, 160, 0.05)", "rgba(60, 70, 120, 0.03)")


def generate_new_tab_html():
    """Return HTML for a styled new-tab page with search and quick links."""
    _refresh_colors()
    bookmarks = storage.load_bookmarks()[:8]
    settings = storage.load_settings()
    search_url = settings.get("search_engine", "https://duckduckgo.com/?q={}")

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

    # Daily quote
    quote_text, quote_author = _daily_quote()
    quote_text_esc = html_mod.escape(quote_text)
    quote_author_esc = html_mod.escape(quote_author)

    # Time-aware ambient gradient
    glow_inner, glow_outer = _time_gradient()

    # Wallpaper
    wallpaper_url = _wallpaper_data_url(settings)
    wallpaper_css = ""
    if wallpaper_url:
        wallpaper_css = f"""
  .wallpaper {{
    position: fixed; top: 0; left: 0;
    width: 100vw; height: 100vh;
    background: url('{wallpaper_url}') center/cover no-repeat;
    z-index: 0;
  }}
  .wallpaper-overlay {{
    position: fixed; top: 0; left: 0;
    width: 100vw; height: 100vh;
    background: rgba(12, 11, 16, 0.7);
    backdrop-filter: blur(2px);
    z-index: 0;
  }}
  body {{ background: transparent; }}
"""

    # Bookmark cards with favicons
    bookmark_cards = ""
    for bm in bookmarks:
        title = bm["title"][:22] or bm["url"][:22]
        url = bm["url"]
        domain = url.split("//")[-1].split("/")[0] if "//" in url else url[:30]
        first_letter = title[0].upper() if title else domain[0].upper()
        # Fetch favicon directly from the site — no third-party service
        scheme = "https" if url.startswith("https") else "http"
        favicon_url = f"{scheme}://{domain}/favicon.ico"
        bookmark_cards += f"""
            <a href="{html_mod.escape(url)}" class="card">
                <div class="card-icon">
                    <img src="{favicon_url}" alt="" class="favicon"
                         onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                    <span class="favicon-fallback">{first_letter}</span>
                </div>
                <div class="card-label">{html_mod.escape(title)}</div>
                <div class="card-domain">{html_mod.escape(domain)}</div>
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
    padding-top: 20vh;
    overflow-x: hidden;
  }}

  /* ── Wallpaper ── */
  {wallpaper_css}

  /* ── Time-aware atmospheric background ── */
  .bg-glow {{
    position: fixed;
    top: 20%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 1000px;
    height: 700px;
    background: radial-gradient(
      ellipse at 45% 45%,
      {glow_inner} 0%,
      {glow_outer} 40%,
      transparent 70%
    );
    pointer-events: none;
    z-index: 1;
    animation: glowPulse 8s ease-in-out infinite alternate;
  }}

  @keyframes glowPulse {{
    0%   {{ opacity: 0.8; transform: translate(-50%, -50%) scale(1); }}
    100% {{ opacity: 1;   transform: translate(-50%, -50%) scale(1.08); }}
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
    background-size: 200% 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 14px;
    user-select: none;
    animation: wordmarkShift 6s ease-in-out infinite alternate;
  }}

  @keyframes wordmarkShift {{
    0%   {{ background-position: 0% 50%; }}
    100% {{ background-position: 100% 50%; }}
  }}

  /* ── Divider with shimmer ── */
  .divider {{
    width: 60px;
    height: 2px;
    background: linear-gradient(90deg, transparent, {ACCENT}, transparent);
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
    border-radius: 1px;
  }}

  .divider::after {{
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.4) 50%,
      transparent 100%
    );
    animation: shimmer 3s ease-in-out infinite;
  }}

  @keyframes shimmer {{
    0%   {{ left: -100%; }}
    60%  {{ left: 200%; }}
    100% {{ left: 200%; }}
  }}

  /* ── Quote ── */
  .quote {{
    max-width: 480px;
    text-align: center;
    margin-bottom: 36px;
    padding: 0 20px;
  }}

  .quote-text {{
    font-size: 13px;
    font-style: italic;
    color: {TEXT_DIM};
    line-height: 1.6;
    margin-bottom: 6px;
  }}

  .quote-author {{
    font-size: 11px;
    color: {TEXT_FAINT};
    letter-spacing: 1px;
  }}

  /* ── Search ── */
  .search-container {{
    width: 560px;
    max-width: 88vw;
    margin-bottom: 48px;
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
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
  }}

  .card:hover {{
    background: rgba(38, 36, 48, 0.85);
    border-color: rgba(205, 141, 106, 0.3);
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.3),
                0 0 0 1px rgba(205, 141, 106, 0.1);
  }}

  .card-icon {{
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(145deg, {ACCENT}, #a06b4c);
    color: {BG_DARK};
    font-size: 18px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 10px;
    user-select: none;
    overflow: hidden;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
  }}

  .card:hover .card-icon {{
    transform: scale(1.08);
    box-shadow: 0 4px 12px rgba(205, 141, 106, 0.3);
  }}

  .favicon {{
    width: 28px;
    height: 28px;
    border-radius: 4px;
    object-fit: contain;
  }}

  .favicon-fallback {{
    display: none;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    font-size: 18px;
    font-weight: 700;
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
  .wordmark           {{ animation: fadeIn 0.5s ease 0.10s both, wordmarkShift 6s ease-in-out 0.5s infinite alternate; }}
  .divider            {{ animation: fadeIn 0.5s ease 0.15s both; }}
  .quote              {{ animation: fadeIn 0.5s ease 0.20s both; }}
  .search-container   {{ animation: fadeIn 0.5s ease 0.26s both; }}
  .quick-links, .empty {{ animation: fadeIn 0.5s ease 0.34s both; }}

  /* ── Staggered card entrance ── */
  .card {{
    opacity: 0;
    animation: fadeIn 0.4s ease both;
  }}
  .card:nth-child(1) {{ animation-delay: 0.38s; }}
  .card:nth-child(2) {{ animation-delay: 0.42s; }}
  .card:nth-child(3) {{ animation-delay: 0.46s; }}
  .card:nth-child(4) {{ animation-delay: 0.50s; }}
  .card:nth-child(5) {{ animation-delay: 0.54s; }}
  .card:nth-child(6) {{ animation-delay: 0.58s; }}
  .card:nth-child(7) {{ animation-delay: 0.62s; }}
  .card:nth-child(8) {{ animation-delay: 0.66s; }}
</style>
</head>
<body>
  {"<div class='wallpaper'></div><div class='wallpaper-overlay'></div>" if wallpaper_url else ""}
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

    <div class="quote">
      <div class="quote-text">&ldquo;{quote_text_esc}&rdquo;</div>
      <div class="quote-author">&mdash; {quote_author_esc}</div>
    </div>

    <div class="search-container">
      <form id="searchform" onsubmit="return handleSearch(event)">
        <input type="text" id="searchbox" placeholder="Search or enter URL\u2026" autofocus>
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <circle cx="11" cy="11" r="7"/>
          <path d="m20 20-4-4"/>
        </svg>
      </form>
    </div>
    <script>
    document.addEventListener('keydown', function(e) {{
      var box = document.getElementById('searchbox');
      if (document.activeElement === box) return;
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (e.key.length === 1) {{
        box.focus();
      }}
    }});
    function handleSearch(e) {{
      e.preventDefault();
      var q = document.getElementById('searchbox').value.trim();
      if (!q) return;
      var hasScheme = new RegExp('^(https?|file|shroud)://', 'i').test(q);
      var looksLikeUrl = hasScheme
        || (q.indexOf('.') !== -1 && q.indexOf(' ') === -1)
        || q.startsWith('localhost')
        || q.startsWith('127.0.0.1')
        || q.startsWith('[::1]');
      var dest;
      if (looksLikeUrl) {{
        if (!hasScheme) {{
          q = (q.indexOf('.') !== -1 ? 'https://' : 'http://') + q;
        }}
        dest = q;
      }} else {{
        var searchUrl = "{search_url}";
        dest = searchUrl.replace("{{}}", encodeURIComponent(q));
      }}
      window.location.hash = "navigate:" + dest;
    }}
    </script>

    {bookmarks_section}
  </div>
</body>
</html>"""
