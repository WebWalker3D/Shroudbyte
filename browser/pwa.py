"""PWA (Progressive Web App) support — manifest detection, install, desktop integration."""

import hashlib
import json
import os
import ssl
import threading
import urllib.request
import urllib.parse
from pathlib import Path

from . import storage

_ICONS_DIR = storage.DATA_DIR / "pwa_icons"


def detect_manifest_js():
    """Return JS that detects a web app manifest and sends it back via console.log."""
    return """(function() {
    if (window.__shroudPWADetected) return;
    window.__shroudPWADetected = true;
    var link = document.querySelector('link[rel="manifest"]');
    if (!link) return;
    var href = link.href;
    if (!href) return;
    fetch(href).then(function(r) { return r.json(); }).then(function(manifest) {
        console.log('__SHROUD_PWA__:' + JSON.stringify({
            action: 'manifest',
            manifest: manifest,
            manifest_url: href,
            page_url: location.href
        }));
    }).catch(function() {});
})();"""


def install_pwa(manifest: dict, page_url: str, manifest_url: str):
    """Install a PWA: save metadata, download icon, create .desktop file."""
    name = manifest.get("name") or manifest.get("short_name") or "Web App"
    short_name = manifest.get("short_name") or name
    start_url = manifest.get("start_url", page_url)
    display = manifest.get("display", "standalone")
    bg_color = manifest.get("background_color", "#0c0b10")
    theme_color = manifest.get("theme_color", "#0c0b10")

    # Resolve relative start_url against manifest URL
    if start_url and not start_url.startswith("http"):
        start_url = urllib.parse.urljoin(manifest_url, start_url)

    # Pick the best icon
    icon_path = ""
    icons = manifest.get("icons", [])
    if icons:
        # Prefer 192x192 or largest
        best = None
        best_size = 0
        for icon in icons:
            sizes = icon.get("sizes", "0x0")
            try:
                w = int(sizes.split("x")[0])
            except (ValueError, IndexError):
                w = 0
            if w > best_size:
                best_size = w
                best = icon
        if best:
            icon_url = best.get("src", "")
            if icon_url and not icon_url.startswith("http"):
                icon_url = urllib.parse.urljoin(manifest_url, icon_url)
            if icon_url:
                icon_path = _download_icon(icon_url, start_url)

    # Save to storage
    app_data = {
        "name": name,
        "short_name": short_name,
        "start_url": start_url,
        "display": display,
        "bg_color": bg_color,
        "theme_color": theme_color,
        "icon_path": icon_path,
        "manifest_url": manifest_url,
        "installed": __import__("time").time(),
    }
    storage.add_installed_app(app_data)

    # Create .desktop file
    _create_desktop_file(app_data)

    return app_data


def uninstall_pwa(start_url: str):
    """Remove a PWA: delete .desktop file and icon."""
    app = storage.get_installed_app(start_url)
    if app:
        # Remove desktop file
        desktop_id = _desktop_id(start_url)
        desktop_path = Path.home() / ".local" / "share" / "applications" / f"{desktop_id}.desktop"
        if desktop_path.exists():
            desktop_path.unlink()

        # Remove icon
        icon_path = app.get("icon_path", "")
        if icon_path and os.path.exists(icon_path):
            os.unlink(icon_path)

    storage.remove_installed_app(start_url)


def _desktop_id(start_url: str) -> str:
    return "shroudbyte-pwa-" + hashlib.sha256(start_url.encode()).hexdigest()[:12]


def _download_icon(icon_url: str, start_url: str) -> str:
    """Download a PWA icon and return the local path."""
    _ICONS_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(urllib.parse.urlparse(icon_url).path).suffix or ".png"
    icon_id = hashlib.sha256(start_url.encode()).hexdigest()[:12]
    local_path = _ICONS_DIR / f"{icon_id}{ext}"

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(icon_url, headers={
            "User-Agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            local_path.write_bytes(resp.read())
        return str(local_path)
    except Exception:
        return ""


def _create_desktop_file(app: dict):
    """Create a .desktop file for the installed PWA."""
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)

    desktop_id = _desktop_id(app["start_url"])
    desktop_path = apps_dir / f"{desktop_id}.desktop"

    # Find the browser executable
    import sys
    python = sys.executable or "python3"
    browser_dir = str(Path(__file__).parent.parent)

    icon_line = f'Icon={app["icon_path"]}' if app.get("icon_path") else "Icon=web-browser"

    content = f"""[Desktop Entry]
Type=Application
Name={app['name']}
Comment=Installed via Shroudbyte
Exec={python} -m browser --app="{app['start_url']}"
Path={browser_dir}
{icon_line}
Terminal=false
Categories=Network;WebBrowser;
StartupWMClass=shroudbyte-pwa
"""
    desktop_path.write_text(content)
    os.chmod(desktop_path, 0o755)
