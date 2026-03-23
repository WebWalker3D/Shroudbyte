#!/usr/bin/env bash
# Build an AppImage for Shroudbyte Browser
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build/appimage"
APP_DIR="$BUILD_DIR/Shroudbyte.AppDir"

echo "=== Building Shroudbyte AppImage ==="

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$APP_DIR/usr"

# Install into AppDir
cd "$PROJECT_DIR"
pip install --prefix="$APP_DIR/usr" --no-warn-script-location .

# AppRun entry point
cat > "$APP_DIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$PATH"
export PYTHONPATH="$HERE/usr/lib/python3/dist-packages:$PYTHONPATH"
exec python3 -m browser "$@"
APPRUN
chmod +x "$APP_DIR/AppRun"

# Desktop file
cat > "$APP_DIR/shroudbyte.desktop" << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=Shroudbyte
Comment=Privacy-focused web browser
Exec=shroudbyte
Icon=shroudbyte
Categories=Network;WebBrowser;
MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;
DESKTOP

# Placeholder icon (replace with real icon)
touch "$APP_DIR/shroudbyte.png"

echo "=== AppDir prepared at $APP_DIR ==="
echo "Run appimagetool to create the final AppImage:"
echo "  appimagetool $APP_DIR Shroudbyte-x86_64.AppImage"
