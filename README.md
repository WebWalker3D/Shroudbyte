# Shroudbyte

A privacy-focused web browser built with PyQt6 and Chromium (QtWebEngine) for Linux. Features things no other browser does: link intelligence, page change monitoring, form draft auto-save, annoyance shield, scroll position memory, clipboard history, screen time tracking, offline page snapshots, and a unified internal page system.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![License](https://img.shields.io/badge/License-GPLv3-green)
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
- **Command Palette** (`Ctrl+K`) -- Quick launcher for browser actions, settings, and navigation.
- **PWA Support** -- Install Progressive Web Apps with desktop integration. Installed apps launch in a minimal window without browser chrome. Manage at `shroud://apps`.
- **WARC/WACZ Capture** -- Record browsing sessions as replayable WARC/WACZ archives for archival or forensic use.
- **Content Script Extensions** -- Minimal extension system supporting manifest.json-based JS/CSS injection. Manage at `shroud://extensions`.
- **Browser Profiles** -- Separate containers with independent cookie jars and storage. Color-coded tab indicators. Manage at `shroud://profiles`.
- **Named Sessions** -- Save and load complete browsing sessions by name. Manage at `shroud://sessions`.
- **Per-Site Settings** -- Fine-grained per-site controls for JavaScript, cookies, images, autoplay, fingerprint resistance, referrer policy, and WebRTC.
- **Permission Ledger** (`shroud://permissions`) -- Audit log of site permission usage with anomaly detection and auto-expire TTL.
- **Download Verification** -- Verify download integrity via SHA-256/512 and MD5 hash checking.
- **Encrypted Export/Import** -- Export and import browser state as password-protected encrypted archives.
- **Address Autofill** (`shroud://addresses`) -- Saved address profiles (Home, Work, etc.) for autofilling any form whose inputs declare standard HTML `autocomplete="..."` attributes (name, street-address, postal-code, email, tel, etc.). Encrypted with the password-vault key when the vault is unlocked. `Ctrl+Shift+A` opens the chooser.
- **Tab Hibernation** -- Optional automatic discard of inactive tab content to bound memory use. Hibernated tabs become lightweight placeholders that reload when clicked. Configurable per-minute idle threshold; off by default.
- **Bookmark Bar** -- Optional always-on toolbar of top bookmarks. Toggle with `Ctrl+Alt+B` or under Bookmarks > Toggle Bookmarks Bar.
- **Dockable DevTools** -- DevTools open in a right-side dock instead of a separate tab; movable, floatable, and toggles closed when re-invoked.
- **High-Contrast Theme** -- WCAG-leaning palette (pure black/white with saturated yellow focus colors) alongside Dark and Light.
- **Crash Log Viewer** (`shroud://crashes`) -- Read past crashes inline as collapsible per-crash blocks; the crash dialog itself offers explicit Copy-to-clipboard and Open-log-folder actions (Shroudbyte never uploads).
- **Crash Recovery Prompt** -- On detecting an ungraceful shutdown, the next launch offers Restore tabs / Start fresh / View log instead of silently re-loading whatever caused the crash.
- **Drag-and-Drop URLs** -- Drag a link from another app onto the tab bar to open it as a new tab.
- **Window State Memory** -- Window size, maximized, and fullscreen state are restored across launches, with a multi-monitor sanity check that prevents windows from landing on a disconnected display.
- **Opt-in Update Check** -- Once-per-day GitHub Releases query when explicitly enabled in settings. Off by default; banner appears on `shroud://about` when a newer version is available.

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
- **Encrypted Password Vault** -- AES-256-GCM encryption with Argon2id key derivation, auto-fill and save prompts. OS keyring backend supported. Auto-migrates from legacy AES-128-CBC/PBKDF2.
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
| `shroud://apps` | Installed PWA app manager |
| `shroud://permissions` | Permission ledger with audit log |
| `shroud://background` | Background activity (service workers, push subscriptions) |
| `shroud://captures` | WARC/WACZ capture status |
| `shroud://extensions` | Content script extensions manager |
| `shroud://profiles` | Browser profiles/containers |
| `shroud://sessions` | Named session management |
| `shroud://addresses` | Saved address profiles for form autofill |
| `shroud://crashes` | Local crash log viewer (no upload) |

All internal pages share a consistent sidebar with cross-page navigation.

## Requirements

- Python 3.11+
- PyQt6 >= 6.5.0
- PyQt6-WebEngine >= 6.5.0
- cryptography >= 41.0.0
- argon2-cffi >= 23.1.0
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

# Launch a PWA in app mode:
python3 -m browser --app=https://example.com
```

## Testing

```bash
pytest                          # run all tests
pytest tests/test_adblock.py    # run a specific file
```

Tests are isolated via a fixture that redirects all storage I/O to a temporary directory.

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
| Toggle Bookmarks Bar | Ctrl+Alt+B |
| Downloads | Ctrl+J |
| Password Manager | Ctrl+Shift+M |
| Auto-fill Password | Ctrl+Shift+L |
| Fill Address | Ctrl+Shift+A |
| Print | Ctrl+P |
| Save as PDF | Ctrl+Shift+S |
| Screenshot | Ctrl+Shift+E |
| New Window | Ctrl+N |
| New Private Window | Ctrl+Shift+P |
| Quit | Ctrl+Q |
| Toggle Menu Bar | Alt |
| Command Palette | Ctrl+K |

## Data Storage

All browser data is stored in `~/.shroudbyte/` (override with `SHROUDBYTE_DATA_DIR` environment variable). Uses a hybrid storage approach: JSON files for low-traffic configuration, SQLite for high-traffic data.

```
~/.shroudbyte/
├── shroudbyte.db             # SQLite (history, screen time, scroll positions, form drafts, permission log)
├── bookmarks.json
├── settings.json
├── session.json
├── window_state.json         # Last window geometry + maximized/fullscreen
├── passwords.enc
├── addresses.dat             # Encrypted when vault is unlocked; plain JSON otherwise
├── blocked_hosts.txt
├── filter_settings.json
├── site_exceptions.json
├── watches.json
├── saved_pages.json
├── cookie_whitelist.json
├── permissions.json
├── update_check.json         # Cached opt-in update query result
├── crash.log                 # Local crash log (never uploaded)
├── .running                  # Marker for detecting unclean shutdowns
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
├── __main__.py          # Entry point, DNS config, Qt app setup, PWA app mode
├── mainwindow.py        # Main window shell, toolbar, tab bar, status bar (~800 lines)
├── mixins/              # MainWindow mixin modules
│   ├── tabs.py          # Tab context menu, pinning, muting, detaching, notes
│   ├── navigation.py    # URL/search input, home navigation, reader mode
│   ├── content_blocking.py  # Loading indicators, ad blocking JS, cosmetic filters
│   ├── password_manager.py  # Password vault locking, auto-fill, auto-lock
│   ├── page_features.py     # Page Watcher, Link Intel, Form Drafts, PWA
│   ├── settings.py      # Settings dialog and runtime application
│   ├── browser_actions.py   # History, downloads, printing, PDF, screenshots
│   ├── data_management.py   # Filter lists, cookies, permissions, bookmarks I/O, PiP
│   └── session.py       # Session save/restore and autosave
├── scheme.py            # shroud:// URL scheme handler (19 internal pages)
├── addresses.py         # Saved address profiles for form autofill
├── updater.py           # Opt-in GitHub release update check
├── i18n.py              # gettext scaffolding for translations
├── webview_ipc.py       # Dispatch table for injected-JS console messages
├── adblock.py           # Network request interceptor, per-page tracking, site exceptions
├── adblock_engine.py    # Enhanced ABP-style filter engine with scriptlet support
├── filterlists.py       # Filter list download, parsing, cosmetic CSS generation
├── fingerprint.py       # Fingerprint resistance JavaScript injection
├── annoyance_shield.py  # Modal/overlay/widget killer JavaScript injection
├── link_intel.py        # Link Intelligence redirect chain resolver
├── pagewatcher.py       # Background page change monitoring engine
├── screentime.py        # Per-domain browsing time tracker
├── clipboard_history.py # In-memory clipboard history tracker
├── privacy_panel.py     # Privacy Dashboard dialog (per-site controls)
├── webview.py           # Custom QWebEngineView and QWebEnginePage
├── storage.py           # JSON persistence for settings, bookmarks, session, etc.
├── db.py                # SQLite backend for history, screen time, scroll, drafts
├── crypto.py            # Argon2id KDF and AES-256-GCM encryption primitives
├── downloads.py         # Download manager
├── download_verify.py   # Download hash verification (SHA-256/512, MD5)
├── passwords.py         # Encrypted password vault (Argon2id + AES-256-GCM)
├── passworddialogs.py   # Password UI (save bar, autofill bar, manager)
├── pwa.py               # PWA manifest detection, install, desktop integration
├── appwindow.py         # Minimal PWA app window (no tabs/URL bar)
├── profiles.py          # Browser profiles/containers with separate storage
├── session_manager.py   # Named session save/load
├── site_settings.py     # Per-site overrides (JS, cookies, autoplay, etc.)
├── extensions.py        # Content script extension system (manifest.json JS/CSS)
├── warc_capture.py      # WARC/WACZ browsing session capture
├── export.py            # Encrypted browser state export/import
├── permission_ledger.py # Permission usage audit log with anomaly detection
├── background_activity.py # Service worker and push subscription tracking
├── newtab.py            # New tab page with search and quick links
├── reader.py            # Reader mode content extraction
├── style.py             # Dark / Light / High-contrast theme palettes
├── dns_proxy.py         # Local SOCKS5 proxy for Shroud DNS
├── dns_auth.py          # HMAC-authenticated DNS query client
├── keyring_backend.py   # OS keyring abstraction for secret storage
└── crashhandler.py      # Global crash handler with logging

tests/                   # 436 tests covering ~80% of modules
├── conftest.py          # Shared fixtures (tmp data dir isolation, DB reset)
├── test_adblock.py
├── test_adblock_engine.py
├── test_addresses.py
├── test_annoyance_shield.py
├── test_background_activity.py
├── test_clipboard.py
├── test_crashhandler.py
├── test_crypto.py
├── test_db.py
├── test_dns_auth.py
├── test_dns_proxy.py
├── test_download_verify.py
├── test_export.py
├── test_extensions.py
├── test_filterlists.py
├── test_fingerprint.py
├── test_i18n.py
├── test_keyring_backend.py
├── test_link_intel.py
├── test_newtab.py
├── test_pagewatcher.py
├── test_passwords.py
├── test_permission_ledger.py
├── test_profiles.py
├── test_pwa.py
├── test_reader.py
├── test_scheme_pages.py        # smoke-renders every shroud:// page
├── test_screentime.py
├── test_session_manager.py
├── test_site_settings.py
├── test_storage.py
├── test_style.py
├── test_tab_hibernation.py
├── test_updater.py
├── test_warc_capture.py
└── test_webview_ipc.py

scripts/
├── build-appimage.sh    # AppImage build script (downloads appimagetool)
└── extract-i18n.sh      # xgettext wrapper for translators
```

## Continuous integration

`.github/workflows/tests.yml` runs the test suite on every push and pull
request against Python 3.11 and 3.12, with Qt in `offscreen` mode so
WebEngine doesn't need a display server.
