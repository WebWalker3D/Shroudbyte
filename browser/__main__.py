"""Entry point for Blade Browser."""

import os
import sys

# QtWebEngine (Chromium) refuses to run as root without disabling its sandbox.
# This is safe for a personal desktop browser.
if os.getuid() == 0:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + " --no-sandbox"
    )

# GPU / WebGL performance flags — must be set before QApplication is created.
_gpu_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
_gpu_flags += " --enable-gpu-rasterization"
_gpu_flags += " --enable-zero-copy"
_gpu_flags += " --enable-features=CanvasOopRasterization"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _gpu_flags.strip()

# DNS-over-HTTPS — must be configured before QApplication is created
# because Chromium parses these flags at startup.
from . import storage as _storage
_doh_settings = _storage.load_settings()
_doh_mode = _doh_settings.get("dns_over_https", "automatic")
_doh_provider = _doh_settings.get("dns_over_https_provider", "https://dns.cloudflare.com/dns-query")

if _doh_mode != "off":
    _chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    _chromium_flags += " --enable-features=DnsOverHttps"
    _chromium_flags += f" --dns-over-https-mode={_doh_mode}"
    if _doh_mode == "secure" and _doh_provider:
        _chromium_flags += f" --dns-over-https-templates={_doh_provider}"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _chromium_flags.strip()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from . import __app_name__
from .mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName("BladeBrowser")

    # Dark palette for dialogs and system widgets
    from PyQt6.QtGui import QPalette, QColor

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(238, 238, 238))
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(43, 43, 43))
    palette.setColor(QPalette.ColorRole.Text, QColor(238, 238, 238))
    palette.setColor(QPalette.ColorRole.Button, QColor(43, 43, 43))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(238, 238, 238))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(41, 121, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, QColor(41, 121, 255))
    app.setPalette(palette)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
