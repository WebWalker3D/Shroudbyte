# Blade Browser

A privacy-focused web browser built with PyQt6 and Chromium (QtWebEngine) for Linux.

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
- View source and developer tools
- Print and save as PDF
- Customizable search engine (default: DuckDuckGo)
- Custom homepage
- Zoom controls (25–500%)
- Private browsing mode

### Privacy & Security
- **Ad & Tracker Blocker** — 111+ hardcoded blocked domains plus downloadable filter lists (EasyList, EasyPrivacy, Fanboy's Annoyance, Peter Lowe's, URLhaus)
- **Cosmetic Filtering** — Hides ad elements and cookie banners via CSS injection with MutationObserver for dynamically added content
- **Script Blocking** — Intercepts ad script creation at document load time
- **Tracking Parameter Stripping** — Removes `utm_*`, `fbclid`, `gclid`, `msclkid`, and 30+ other tracking parameters from URLs
- **DNS-over-HTTPS** — Cloudflare DoH by default, with off/automatic/secure modes and custom provider support
- **Fingerprint Resistance** — Optional spoofing of Canvas, WebGL, AudioContext, hardware concurrency, device memory, and screen resolution
- **HTTPS-Only Mode** — Optional enforcement of HTTPS connections
- **Do Not Track** — Sends DNT header on all requests
- **Encrypted Password Vault** — AES-128-CBC + HMAC encryption with PBKDF2-derived master key, auto-fill and save prompts
- **Clear Browsing Data** — Bulk clear history, cookies, cache, and passwords

### Filter Lists
| List | Default |
|------|---------|
| EasyList | Enabled |
| EasyPrivacy | Enabled |
| Fanboy's Annoyance List | Enabled |
| Fanboy's Social Blocking | Disabled |
| Peter Lowe's Ad Server List | Enabled |
| URLhaus Malicious URL Blocklist | Enabled |

## Requirements

- Python 3.10+
- PyQt6 >= 6.5.0
- PyQt6-WebEngine >= 6.5.0
- cryptography >= 41.0.0

## Installation

```bash
git clone git@github.com:WebWalker3D/Blade-Browser.git
cd Blade-Browser
pip install -r requirements.txt
```

### Desktop Entry (optional)

Copy the desktop file and launcher script to integrate with your desktop environment:

```bash
cp blade-browser.desktop ~/.local/share/applications/
chmod +x blade-browser.sh
```

Edit `blade-browser.desktop` and `blade-browser.sh` to match your install path.

## Usage

```bash
# Any of these work:
python3 -m browser
python3 run.py
./blade-browser.sh
```

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New Tab | Ctrl+T |
| Close Tab | Ctrl+W |
| Reopen Closed Tab | Ctrl+Shift+T |
| Switch to Tab 1–9 | Alt+1–9 |
| Focus Address Bar | Ctrl+L / F6 |
| Find in Page | Ctrl+F |
| Reload | F5 / Ctrl+R |
| Hard Reload | Ctrl+Shift+R |
| Zoom In / Out / Reset | Ctrl+= / Ctrl+- / Ctrl+0 |
| Full Screen | F11 |
| View Source | Ctrl+U |
| Developer Tools | F12 |
| History | Ctrl+H |
| Bookmark Page | Ctrl+D |
| All Bookmarks | Ctrl+Shift+B |
| Downloads | Ctrl+J |
| Password Manager | Ctrl+Shift+M |
| Auto-fill Password | Ctrl+Shift+L |
| Print | Ctrl+P |
| Save as PDF | Ctrl+Shift+S |
| New Window | Ctrl+N |
| New Private Window | Ctrl+Shift+P |
| Quit | Ctrl+Q |
| Toggle Menu Bar | Alt |

## Data Storage

All browser data is stored in `~/.blade-browser/` (override with `BLADE_DATA_DIR` environment variable):

```
~/.blade-browser/
├── bookmarks.json
├── history.json
├── settings.json
├── session.json
├── passwords.enc
├── blocked_hosts.txt
├── filter_settings.json
└── filters/
    ├── easylist.txt
    ├── easyprivacy.txt
    └── ...
```

## Architecture

```
browser/
├── __main__.py       # Entry point, DNS-over-HTTPS config, Qt app setup
├── mainwindow.py     # Main window, tabs, toolbar, UI, content blocking injection
├── adblock.py        # Network-level request interceptor, DNT, param stripping
├── filterlists.py    # Filter list download, parsing, cosmetic CSS generation
├── fingerprint.py    # Fingerprint resistance JavaScript injection
├── webview.py        # Custom QWebEngineView and QWebEnginePage
├── storage.py        # Persistent settings, bookmarks, history, hosts
├── downloads.py      # Download manager
├── passwords.py      # Encrypted password vault
├── passworddialogs.py# Password UI dialogs
├── newtab.py         # New tab page with search and quick links
└── style.py          # Dark theme colors and stylesheets
```
