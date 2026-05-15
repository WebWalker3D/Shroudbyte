#!/usr/bin/env bash
# Build an AppImage for Shroudbyte Browser.
#
# Requires: python3, pip, and one of: appimagetool (or downloads it),
# plus rsvg-convert or ImageMagick (`magick`/`convert`) to rasterize
# the icon if a PNG isn't already present.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build/appimage"
APP_DIR="$BUILD_DIR/Shroudbyte.AppDir"
ARCH="${ARCH:-x86_64}"
OUT_FILE="${OUT_FILE:-$BUILD_DIR/Shroudbyte-${ARCH}.AppImage}"

echo "=== Building Shroudbyte AppImage ==="

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$APP_DIR/usr"

# Install into AppDir
cd "$PROJECT_DIR"
pip install --prefix="$APP_DIR/usr" --no-warn-script-location .

# AppRun entry point — find the bundled site-packages dynamically so the
# AppImage works on whatever Python version pip ended up installing into.
cat > "$APP_DIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$PATH"
# Add every site-packages directory under usr/lib to PYTHONPATH.
EXTRA=$(find "$HERE/usr/lib" -maxdepth 3 -type d \
    \( -name "site-packages" -o -name "dist-packages" \) 2>/dev/null \
    | tr '\n' ':')
export PYTHONPATH="${EXTRA}${PYTHONPATH:-}"
exec python3 -m browser "$@"
APPRUN
chmod +x "$APP_DIR/AppRun"

# Desktop file (AppImage requires the .desktop file at the AppDir root
# AND a usr/share/applications copy for the embedded metadata to be
# picked up by xdg utilities once extracted).
cat > "$APP_DIR/shroudbyte.desktop" << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=Shroudbyte
Comment=Privacy-focused web browser
Exec=shroudbyte %U
Icon=shroudbyte
Categories=Network;WebBrowser;
MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;
StartupNotify=true
StartupWMClass=Shroudbyte
DESKTOP
mkdir -p "$APP_DIR/usr/share/applications"
cp "$APP_DIR/shroudbyte.desktop" "$APP_DIR/usr/share/applications/"

# Icon: rasterize the SVG to PNG (AppImage requires a real PNG/XPM, not
# a zero-byte placeholder, or the resulting binary fails to mount).
ICON_SVG="$PROJECT_DIR/shroudbyte-icon.svg"
ICON_PNG="$APP_DIR/shroudbyte.png"
ICON_SIZE=256
if [[ -f "$ICON_SVG" ]]; then
    if command -v rsvg-convert >/dev/null 2>&1; then
        rsvg-convert -w "$ICON_SIZE" -h "$ICON_SIZE" "$ICON_SVG" -o "$ICON_PNG"
    elif command -v magick >/dev/null 2>&1; then
        magick -background none -density 384 \
            "$ICON_SVG" -resize "${ICON_SIZE}x${ICON_SIZE}" "$ICON_PNG"
    elif command -v convert >/dev/null 2>&1; then
        convert -background none -density 384 \
            "$ICON_SVG" -resize "${ICON_SIZE}x${ICON_SIZE}" "$ICON_PNG"
    else
        echo "ERROR: need rsvg-convert or ImageMagick to rasterize $ICON_SVG" >&2
        exit 1
    fi
elif [[ -f "$PROJECT_DIR/shroudbyte.png" ]]; then
    cp "$PROJECT_DIR/shroudbyte.png" "$ICON_PNG"
else
    echo "ERROR: no shroudbyte-icon.svg or shroudbyte.png found in $PROJECT_DIR" >&2
    exit 1
fi
mkdir -p "$APP_DIR/usr/share/icons/hicolor/${ICON_SIZE}x${ICON_SIZE}/apps"
cp "$ICON_PNG" \
   "$APP_DIR/usr/share/icons/hicolor/${ICON_SIZE}x${ICON_SIZE}/apps/shroudbyte.png"

# Bin shim so PATH-resolved invocation works inside the AppImage.
mkdir -p "$APP_DIR/usr/bin"
cat > "$APP_DIR/usr/bin/shroudbyte" << 'SHIM'
#!/bin/bash
exec python3 -m browser "$@"
SHIM
chmod +x "$APP_DIR/usr/bin/shroudbyte"

echo "=== AppDir prepared at $APP_DIR ==="

# Locate or download appimagetool.
APPIMAGETOOL="$(command -v appimagetool || true)"
if [[ -z "$APPIMAGETOOL" ]]; then
    APPIMAGETOOL="$BUILD_DIR/appimagetool"
    if [[ ! -x "$APPIMAGETOOL" ]]; then
        APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
        echo "appimagetool not found on PATH; downloading from $APPIMAGETOOL_URL"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
        elif command -v wget >/dev/null 2>&1; then
            wget -q -O "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
        else
            echo "ERROR: need curl or wget to download appimagetool" >&2
            exit 1
        fi
        chmod +x "$APPIMAGETOOL"
    fi
fi

echo "=== Running appimagetool ==="
ARCH="$ARCH" "$APPIMAGETOOL" "$APP_DIR" "$OUT_FILE"
echo "=== Built: $OUT_FILE ==="
