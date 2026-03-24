"""Reader mode — article extraction and clean reading view."""

from . import style as _style_mod


def _refresh_colors():
    g = globals()
    for _name in (
        "ACCENT", "ACCENT_HOVER", "ACCENT_TEXT", "BG_DARK", "BG_CARD",
        "BG_MID", "TEXT", "TEXT_DIM", "TEXT_FAINT", "BORDER",
    ):
        g[_name] = getattr(_style_mod, _name)


_refresh_colors()

# JavaScript that extracts article content from the current page.
# Returns a dict with {title, byline, content, siteName} or null on failure.
READER_EXTRACT_JS = r"""
(function() {
    // ── Metadata extraction ──
    function getMeta(names) {
        for (var i = 0; i < names.length; i++) {
            var el = document.querySelector(
                'meta[name="' + names[i] + '"], meta[property="' + names[i] + '"]'
            );
            if (el && el.content) return el.content.trim();
        }
        return '';
    }

    var title = '';
    var h1 = document.querySelector('h1');
    if (h1) title = h1.textContent.trim();
    if (!title) title = getMeta(['og:title', 'twitter:title']);
    if (!title) title = document.title || '';

    var byline = getMeta(['author', 'article:author', 'twitter:creator']);
    if (!byline) {
        var byEl = document.querySelector('.byline, .author, [rel="author"], [itemprop="author"]');
        if (byEl) byline = byEl.textContent.trim();
    }

    var siteName = getMeta(['og:site_name']) || location.hostname.replace(/^www\./, '');

    // ── Find the best content node ──
    var candidates = [];

    // Semantic candidates first
    var semantic = document.querySelectorAll(
        'article, [role="article"], [role="main"], main, [itemprop="articleBody"]'
    );
    for (var i = 0; i < semantic.length; i++) {
        candidates.push({node: semantic[i], score: 50});
    }

    // Score all divs/sections
    var blocks = document.querySelectorAll('div, section, td');
    for (var i = 0; i < blocks.length; i++) {
        var node = blocks[i];
        var paras = node.querySelectorAll('p');
        if (paras.length < 2) continue;

        var score = 0;
        var text = '';
        for (var j = 0; j < paras.length; j++) {
            var pText = paras[j].textContent.trim();
            if (pText.length > 30) score += 1;
            text += pText + ' ';
        }
        if (text.length < 200) continue;

        score += Math.min(text.length / 100, 30);

        // Class/id bonuses
        var ci = ((node.className || '') + ' ' + (node.id || '')).toLowerCase();
        if (/article|post|entry|story|content|body|text/.test(ci)) score += 25;
        if (/comment|sidebar|nav|footer|header|menu|ad|social|share|related|widget|promo/.test(ci)) score -= 30;

        // Link density penalty
        var links = node.querySelectorAll('a');
        var linkText = 0;
        for (var j = 0; j < links.length; j++) linkText += links[j].textContent.length;
        var linkDensity = text.length > 0 ? linkText / text.length : 1;
        if (linkDensity > 0.4) score -= 20;

        candidates.push({node: node, score: score});
    }

    if (candidates.length === 0) return null;

    candidates.sort(function(a, b) { return b.score - a.score; });
    var best = candidates[0].node;

    // ── Clean the content ──
    var clone = best.cloneNode(true);

    // Remove unwanted elements
    var removeSelectors = [
        'script', 'style', 'nav', 'aside', 'footer', 'header',
        'iframe', 'form', 'button', 'input', 'select', 'textarea',
        '.sidebar', '.nav', '.menu', '.comment', '.comments',
        '.social', '.share', '.ad', '.ads', '.advertisement',
        '.related', '.widget', '.promo', '.popup', '.modal',
        '[role="navigation"]', '[role="complementary"]', '[role="banner"]',
        '[aria-hidden="true"]'
    ];
    var toRemove = clone.querySelectorAll(removeSelectors.join(','));
    for (var i = toRemove.length - 1; i >= 0; i--) {
        toRemove[i].parentNode.removeChild(toRemove[i]);
    }

    // Remove hidden elements
    var all = clone.querySelectorAll('*');
    for (var i = all.length - 1; i >= 0; i--) {
        var s = window.getComputedStyle(all[i]);
        if (s && s.display === 'none') {
            all[i].parentNode.removeChild(all[i]);
        }
    }

    var content = clone.innerHTML;
    if (content.length < 100) return null;

    return {
        title: title,
        byline: byline,
        content: content,
        siteName: siteName
    };
})()
"""


def generate_reader_html(title, byline, content, site_name, original_url):
    """Produce a styled reader-mode HTML page."""
    _refresh_colors()
    header_parts = []
    if byline:
        header_parts.append(f'<div class="byline">{byline}</div>')
    if site_name:
        header_parts.append(
            f'<div class="site"><a href="{original_url}">{site_name}</a></div>'
        )
    header_meta = "\n".join(header_parts)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: {BG_DARK};
    color: {TEXT};
    font-family: 'Georgia', 'Noto Serif', 'Times New Roman', serif;
    line-height: 1.8;
    padding: 60px 24px 120px;
    overflow-x: hidden;
  }}

  .reader-bar {{
    position: fixed;
    top: 0; left: 0; right: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 24px;
    background: {BG_MID};
    border-bottom: 1px solid {BORDER};
    z-index: 100;
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    font-size: 12px;
    color: {TEXT_FAINT};
  }}

  .reader-bar a {{
    color: {ACCENT};
    text-decoration: none;
    font-size: 12px;
  }}
  .reader-bar a:hover {{
    color: {ACCENT_HOVER};
  }}

  .reader-label {{
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 600;
    font-size: 10px;
    color: {ACCENT};
  }}

  .article {{
    max-width: 680px;
    margin: 0 auto;
  }}

  .article-title {{
    font-size: 32px;
    font-weight: 700;
    line-height: 1.3;
    color: {TEXT};
    margin-bottom: 16px;
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
  }}

  .byline {{
    font-size: 14px;
    color: {TEXT_DIM};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    margin-bottom: 4px;
  }}

  .site {{
    font-size: 13px;
    margin-bottom: 8px;
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
  }}
  .site a {{
    color: {ACCENT};
    text-decoration: none;
  }}
  .site a:hover {{
    color: {ACCENT_HOVER};
  }}

  .divider {{
    width: 50px;
    height: 1px;
    background: linear-gradient(90deg, {ACCENT}, transparent);
    margin: 28px 0 32px;
    opacity: 0.5;
  }}

  /* ── Article content ── */
  .article-body {{
    font-size: 18px;
  }}

  .article-body p {{
    margin-bottom: 1.2em;
  }}

  .article-body h1, .article-body h2, .article-body h3,
  .article-body h4, .article-body h5, .article-body h6 {{
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    color: {TEXT};
    margin: 1.6em 0 0.6em;
    line-height: 1.3;
  }}
  .article-body h1 {{ font-size: 28px; }}
  .article-body h2 {{ font-size: 24px; }}
  .article-body h3 {{ font-size: 20px; }}

  .article-body a {{
    color: {ACCENT};
    text-decoration: underline;
    text-decoration-color: rgba(205, 141, 106, 0.3);
    text-underline-offset: 3px;
  }}
  .article-body a:hover {{
    color: {ACCENT_HOVER};
    text-decoration-color: {ACCENT_HOVER};
  }}

  .article-body img {{
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin: 1em 0;
    display: block;
  }}

  .article-body figure {{
    margin: 1.4em 0;
  }}
  .article-body figcaption {{
    font-size: 13px;
    color: {TEXT_DIM};
    text-align: center;
    margin-top: 8px;
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
  }}

  .article-body blockquote {{
    border-left: 3px solid {ACCENT};
    padding: 8px 0 8px 20px;
    margin: 1.2em 0;
    color: {TEXT_DIM};
    font-style: italic;
  }}

  .article-body pre {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 14px;
    line-height: 1.5;
    margin: 1.2em 0;
  }}

  .article-body code {{
    background: {BG_CARD};
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.9em;
  }}

  .article-body pre code {{
    background: none;
    padding: 0;
  }}

  .article-body ul, .article-body ol {{
    margin: 1em 0;
    padding-left: 1.6em;
  }}

  .article-body li {{
    margin-bottom: 0.4em;
  }}

  .article-body table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1.2em 0;
  }}
  .article-body th, .article-body td {{
    padding: 8px 12px;
    border: 1px solid {BORDER};
    text-align: left;
    font-size: 15px;
  }}
  .article-body th {{
    background: {BG_CARD};
    font-family: 'Cantarell', 'Noto Sans', system-ui, sans-serif;
    font-weight: 600;
  }}

  .article-body hr {{
    border: none;
    height: 1px;
    background: {BORDER};
    margin: 2em 0;
  }}

  /* ── Animations ── */
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .article {{ animation: fadeIn 0.4s ease both; }}
</style>
</head>
<body>
  <div class="reader-bar">
    <span class="reader-label">Reader Mode</span>
    <a href="{original_url}">View original page</a>
  </div>

  <div class="article">
    <h1 class="article-title">{title}</h1>
    {header_meta}
    <div class="divider"></div>
    <div class="article-body">
      {content}
    </div>
  </div>
</body>
</html>"""
