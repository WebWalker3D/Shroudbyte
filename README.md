# Shroudbyte

A privacy-focused web browser built with PyQt6 and Chromium (QtWebEngine) for Linux. Features things no other browser does: link intelligence, page change monitoring, form draft auto-save, annoyance shield, scroll position memory, clipboard history, screen time tracking, offline page snapshots, and a unified internal page system.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Linux-orange)

## Features

### Browsing
- Tabbed browsing with session restore
- URL bar with autocomplete from history and bookmarks
- Bookmarks and browsing history
- Download manager
- Find in page
- Reader mode
- View source with line numbers
- Print and save as PDF
- Screenshot capture
- Private browsing mode
- Tab pinning, muting, and detaching
- Zoom controls (25-500%)

### Features No Other Browser Has

- **Link Intelligence** -- Hover over any link to see where it really goes before you click. Resolves redirect chains, detects tracker domains, URL shorteners, and tracking parameters in a themed tooltip.
- **Privacy Dashboard** (`shroud://privacy`) -- Per-site control panel showing blocked/allowed trackers, cookies, permissions, and stripped tracking parameters. Inline Allow/Block/Delete/Revoke controls with per-site exceptions.
- **Page Watch** (`shroud://watches`) -- Background change monitoring for any page. Right-click a page to watch it; the browser periodically fetches it via HEAD requests and notifies you when content changes, with a visual diff.
- **Form Draft Auto-Save** -- Automatically saves form field values every 30 seconds. When you return to a page with a saved draft, a restore bar offers to repopulate your fields. Recovers from crashes and accidental navigation.
- **Scroll Position Memory** -- Remembers where you were reading on every page. When you return, you resume exactly where you left off. Skips restore on same-page reload so logo clicks still go to top.
- **Annoyance Shield** -- Goes beyond ad blocking to kill the modern web's non-ad annoyances: cookie consent popups (auto-declines via known SDK APIs), chat widgets, newsletter modals, anti-adblock walls, floating video players, app install banners. Heuristic overlay detector kills fixed-position elements covering the viewport.
- **Screen Time** (`shroud://screentime`) -- Opt-in per-domain browsing time tracker. Shows today and 7-day breakdowns with bar charts. Domain-level only, off by default, disabled in private mode.
- **Clipboard History** -- Right-click to access your recent copies. Shows `text:` or `url:` prefixed entries. URLs open in new tabs on click, large text opens a viewer window. In-memory only, never touches disk.
- **Tab Notes** -- Right-click any tab to attach a one-line note. Shows in the tab tooltip with a pin icon. Survives session restores.
- **Tab Search** (`Ctrl+Shift+F`) -- Popup to search and switch between open tabs by title, URL, or note.
- **Tab Group by Site** (`Ctrl+Shift+G`) -- One keystroke to sort all tabs by domain. Same-site tabs cluster together.
- **Duplicate Tab Detection** -- When you navigate to a URL already open in another tab, a bar offers to switch to it instead.
- **Saved Pages** (`shroud://saved`) -- Press `Ctrl+Shift+D` to save any page as an offline snapshot. View saved pages at `shroud://saved` with a toolbar showing the original URL and a link back.
- **Reading Time Estimate** -- Status bar shows estimated reading time for the current page (~N min read).
- **Search Engine Presets** -- 10 privacy-rated search engines with descriptions, grouped as Private (DuckDuckGo, Startpage, Brave, Mojeek, Qwant, Ecosia), Power User (Kagi, Marginalia, Wiby), and Standard (Google, Bing, Yahoo, Yandex).

### Privacy & Security
- **Ad & Tracker Blocker** -- 111+ hardcoded blocked domains plus downloadable filter lists (EasyList, EasyPrivacy, Fanboy's Annoyance, Peter Lowe's, URLhaus). Per-page request tracking with per-site allow/block exceptions.
- **Cosmetic Filtering** -- Hides ad elements and cookie banners via CSS injection with MutationObserver for dynamically added content.
- **Script Blocking** -- Intercepts ad script creation at document load time.
- **Tracking Parameter Stripping** -- Removes `utm_*`, `fbclid`, `gclid`, `msclkid`, and 30+ other tracking parameters from URLs.
- **DNS-over-HTTPS** -- Cloudflare DoH by default, with off/automatic/secure modes and custom provider support.
- **Shroud DNS** -- Optional integration with a self-hosted Shroud DNS server for authenticated DNS resolution via pfSense.
- **Fingerprint Resistance** -- Optional spoofing of Canvas, WebGL, AudioContext, hardware concurrency, device memory, and screen resolution.
- **HTTPS-Only Mode** -- Optional enforcement of HTTPS connections.
- **Do Not Track** -- Sends DNT header on all requests.
- **Encrypted Password Vault** -- AES-128-CBC + HMAC encryption with PBKDF2-derived master key, auto-fill and save prompts. OS keyring backend supported.
- **Auto-Delete Cookies** -- Automatically deletes cookies when you close the last tab for a domain, with a whitelist for sites you want to stay logged into.
- **Clear Browsing Data** -- Bulk clear history, cookies, cache, and passwords.

### Filter Lists
| List | Default |
|------|---------|
| EasyList | Enabled |
| EasyPrivacy | Enabled |
| Fanboy's Annoyance List | Enabled |
| Fanboy's Social Blocking | Disabled |
| Peter Lowe's Ad Server List | Enabled |
| URLhaus Malicious URL Blocklist | Enabled |

### Internal Pages
| Page | Description |
|------|-------------|
| `shroud://newtab` | New tab with search and quick links |
| `shroud://settings` | Browser settings with Firefox-style sidebar layout |
| `shroud://bookmarks` | Bookmarks manager with delete controls |
| `shroud://history` | Searchable browsing history with client-side filtering |
| `shroud://privacy` | Per-site privacy dashboard with tracker/cookie/permission controls |
| `shroud://watches` | Page watch manager with diffs, intervals, and controls |
| `shroud://screentime` | Per-domain screen time dashboard |
| `shroud://saved` | Offline saved pages reading list |
| `shroud://source` | Page source viewer with line numbers |
| `shroud://about` | Browser version and system info |
| `shroud://shortcuts` | Keyboard shortcuts reference |

All internal pages share a consistent sidebar with cross-page navigation.

## Requirements

- Python 3.10+
- PyQt6 >= 6.5.0
- PyQt6-WebEngine >= 6.5.0
- cryptography >= 41.0.0
- keyring >= 24.0.0

## Installation

```bash
git clone git@github.com:WebWalker3D/Shroudbyte.git
cd Shroudbyte
pip install -r requirements.txt
```

### Desktop Entry (optional)

Copy the desktop file and launcher script to integrate with your desktop environment:

```bash
cp shroudbyte.desktop ~/.local/share/applications/
chmod +x shroudbyte.sh
```

Edit `shroudbyte.desktop` and `shroudbyte.sh` to match your install path.

## Usage

```bash
# Any of these work:
python3 -m browser
python3 run.py
./shroudbyte.sh
```

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New Tab | Ctrl+T |
| Close Tab | Ctrl+W |
| Reopen Closed Tab | Ctrl+Shift+T |
| Switch to Tab 1-9 | Alt+1-9 |
| Focus Address Bar | Ctrl+L / F6 |
| Find in Page | Ctrl+F |
| Search Open Tabs | Ctrl+Shift+F |
| Group Tabs by Site | Ctrl+Shift+G |
| Reload | F5 / Ctrl+R |
| Hard Reload | Ctrl+Shift+R |
| Zoom In / Out / Reset | Ctrl+= / Ctrl+- / Ctrl+0 |
| Full Screen | F11 |
| Reader Mode | F9 |
| View Source | Ctrl+U |
| Developer Tools | F12 |
| History | Ctrl+H |
| Bookmark Page | Ctrl+D |
| Save Page Offline | Ctrl+Shift+D |
| All Bookmarks | Ctrl+Shift+B |
| Downloads | Ctrl+J |
| Password Manager | Ctrl+Shift+M |
| Auto-fill Password | Ctrl+Shift+L |
| Print | Ctrl+P |
| Save as PDF | Ctrl+Shift+S |
| Screenshot | Ctrl+Shift+E |
| New Window | Ctrl+N |
| New Private Window | Ctrl+Shift+P |
| Quit | Ctrl+Q |
| Toggle Menu Bar | Alt |

## Data Storage

All browser data is stored in `~/.shroudbyte/` (override with `SHROUDBYTE_DATA_DIR` environment variable):

```
~/.shroudbyte/
├── bookmarks.json
├── history.json
├── settings.json
├── session.json
├── passwords.enc
├── blocked_hosts.txt
├── filter_settings.json
├── site_exceptions.json
├── watches.json
├── saved_pages.json
├── scroll_positions.json
├── form_drafts.json
├── screen_time.json
├── cookie_whitelist.json
├── permissions.json
├── filters/
│   ├── easylist.txt
│   ├── easyprivacy.txt
│   └── ...
├── saved/
│   └── <page-id>.html
├── webengine/
│   └── (Chromium profile data)
└── cache/
    └── (Chromium cache)
```

## Architecture

```
browser/
├── __main__.py          # Entry point, DNS config, Qt app setup
├── mainwindow.py        # Main window, tabs, toolbar, UI, content injection
├── scheme.py            # shroud:// URL scheme handler with shared sidebar layout
├── adblock.py           # Network request interceptor, per-page tracking, site exceptions
├── filterlists.py       # Filter list download, parsing, cosmetic CSS generation
├── fingerprint.py       # Fingerprint resistance JavaScript injection
├── annoyance_shield.py  # Modal/overlay/widget killer JavaScript injection
├── link_intel.py        # Link Intelligence redirect chain resolver
├── pagewatcher.py       # Background page change monitoring engine
├── screentime.py        # Per-domain browsing time tracker
├── clipboard_history.py # In-memory clipboard history tracker
├── privacy_panel.py     # Privacy Dashboard dialog (per-site controls)
├── webview.py           # Custom QWebEngineView and QWebEnginePage
├── storage.py           # Persistent settings, bookmarks, history, watches, drafts
├── downloads.py         # Download manager
├── passwords.py         # Encrypted password vault (AES-128-CBC)
├── passworddialogs.py   # Password UI (save bar, autofill bar, manager)
├── newtab.py            # New tab page with search and quick links
├── reader.py            # Reader mode content extraction
├── style.py             # Dark theme colors and stylesheets
├── dns_proxy.py         # Local SOCKS5 proxy for Shroud DNS
├── dns_auth.py          # HMAC-authenticated DNS query client
├── keyring_backend.py   # OS keyring abstraction for secret storage
└── crashhandler.py      # Global crash handler with logging
```
