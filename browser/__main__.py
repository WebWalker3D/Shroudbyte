"""Entry point for Shroudbyte."""

import ctypes
import ctypes.util
import os
import signal
import subprocess
import sys

# Set the process name so the desktop/app-switcher shows "shroudbyte"
# instead of "python3".  Must happen before QApplication is created.
def _set_process_name(name: str):
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        libc.prctl(15, name.encode(), 0, 0, 0)  # PR_SET_NAME = 15
    except Exception:
        pass

_set_process_name("shroudbyte")

# Install global crash handler as early as possible so that any unhandled
# exception during startup is caught and logged instead of dying silently.
from . import crashhandler as _crashhandler
_crashhandler.install()

# Suppress noisy Chromium/Qt warnings that are not actionable.
os.environ["QT_LOGGING_RULES"] = os.environ.get("QT_LOGGING_RULES", "") + \
    ";qt.qpa.wayland.textinput=false"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = \
    os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + \
    " --disable-features=AutofillServerCommunication" \
    " --disable-gpu-shader-disk-cache" \
    " --force-webrtc-ip-handling-policy=disable_non_proxied_udp" \
    " --reduced-referrer-granularity"

# QtWebEngine (Chromium) refuses to run as root without disabling its sandbox.
# Running a browser as root is dangerous — warn the user loudly.
if os.getuid() == 0:
    print(
        "\033[1;31mWARNING: Running as root is not recommended. "
        "The Chromium sandbox has been disabled.\033[0m",
        file=sys.stderr,
    )
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + " --no-sandbox"
    )

# GPU / WebGL performance flags — must be set before QApplication is created.
_gpu_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
_gpu_flags += " --enable-gpu-rasterization"
_gpu_flags += " --enable-zero-copy"
_gpu_flags += " --enable-features=CanvasOopRasterization"
_gpu_flags += " --disable-gpu-compositing"
_gpu_flags += " --allow-insecure-localhost"
_gpu_flags += " --disable-features=BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessRespectPreflightResults,Translate"
_gpu_flags += " --log-level=3"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _gpu_flags.strip()

# DNS configuration — must be set before QApplication is created
# because Chromium parses these flags at startup.
from . import storage as _storage
_settings = _storage.load_settings()

_proxy_instance = None

_dns_secret = _storage.get_dns_secret(_settings)
_dns_fingerprint = _storage.get_dns_cert_fingerprint(_settings)


def _deferred_dns_secret_migration():
    """Migrate legacy plaintext DNS secrets to keyring (runs after window shown)."""
    if _dns_secret and _settings.get("custom_dns_secret"):
        from . import keyring_backend as _kb
        if _kb.is_available():
            if _kb.store_secret("dns_secret", _dns_secret):
                _settings["custom_dns_secret"] = ""
            if _dns_fingerprint and _kb.store_secret("dns_cert_fingerprint", _dns_fingerprint):
                _settings["custom_dns_cert_fingerprint"] = ""
            _storage.save_settings(_settings)

if _settings.get("custom_dns_enabled") and _settings.get("custom_dns_server") and _dns_secret:
    # Custom authenticated DNS via local SOCKS5 proxy.
    # Settings store the base URL (e.g. https://pfsense:8853); append the
    # query path so the proxy gets the full endpoint.
    from .dns_proxy import ShroudSOCKS5Proxy
    _dns_base = _settings["custom_dns_server"].rstrip("/")
    _proxy_instance = ShroudSOCKS5Proxy(
        pfsense_url=_dns_base + "/shroud-dns-query",
        shared_secret=_dns_secret,
        fallback=_settings.get("custom_dns_fallback", True),
        cert_fingerprint=_dns_fingerprint,
    )
    _proxy_port = _proxy_instance.start()

    _chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    _chromium_flags += f" --proxy-server=socks5://127.0.0.1:{_proxy_port}"
    # Force Chromium to send hostnames (not resolved IPs) to the SOCKS
    # proxy so that DNS is resolved via authenticated DoH.
    # Qt WebEngine splits QTWEBENGINE_CHROMIUM_FLAGS on spaces, so the
    # --host-resolver-rules value cannot contain spaces.  Pass it via
    # sys.argv where each element is preserved as a single argument.
    sys.argv.append(
        "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost , EXCLUDE 127.0.0.1 , EXCLUDE [::1]"
    )
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _chromium_flags.strip()
else:
    # Standard Chromium DNS-over-HTTPS
    _doh_mode = _settings.get("dns_over_https", "automatic")
    _doh_provider = _settings.get("dns_over_https_provider", "https://dns.cloudflare.com/dns-query")

    if _doh_mode != "off":
        _chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        _chromium_flags += " --enable-features=DnsOverHttps"
        _chromium_flags += f" --dns-over-https-mode={_doh_mode}"
        if _doh_mode == "secure" and _doh_provider:
            _chromium_flags += f" --dns-over-https-templates={_doh_provider}"
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _chromium_flags.strip()

# Register the shroud:// scheme before QApplication is created — Qt requires
# custom URL schemes to be registered before the first QGuiApplication instance.
from .scheme import register_shroud_scheme
register_shroud_scheme()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from . import __app_name__
from .mainwindow import MainWindow



def _launch_splash():
    """Launch a lightweight splash window in a separate process.

    Returns the Popen handle so the caller can kill it once the main window
    is ready.  The subprocess uses only basic Qt widgets (no WebEngine) so
    it starts almost instantly.
    """
    script = r"""
import sys
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

app = QApplication(sys.argv)
w = QWidget()
w.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
w.setFixedSize(380, 200)
w.setStyleSheet("background-color: #18181c;")

layout = QVBoxLayout(w)
layout.setContentsMargins(0, 0, 0, 0)
layout.setSpacing(8)

title = QLabel("Shroudbyte")
title.setAlignment(Qt.AlignmentFlag.AlignCenter)
title.setFont(QFont("sans-serif", 22, QFont.Weight.Bold))
title.setStyleSheet("color: #e4e4e9; background: transparent;")

subtitle = QLabel("Loading\u2026")
subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
subtitle.setFont(QFont("sans-serif", 10))
subtitle.setStyleSheet("color: #9494a3; background: transparent;")

layout.addStretch()
layout.addWidget(title)
layout.addWidget(subtitle)
layout.addStretch()

screen = app.primaryScreen()
if screen:
    geo = screen.availableGeometry()
    w.move(geo.center().x() - 190, geo.center().y() - 100)

w.show()
sys.exit(app.exec())
"""
    return subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _parse_app_url():
    """Check for --app=URL argument."""
    for arg in sys.argv[1:]:
        if arg.startswith("--app="):
            return arg[6:]
    return None


def main():
    app_url = _parse_app_url()

    # Launch splash immediately — before any heavy work — so the user
    # sees feedback while settings, DNS proxy, and Qt initialise.
    splash_proc = None
    if not app_url:
        splash_proc = _launch_splash()

    try:
        # Filter out --app= from argv so Chromium doesn't choke on it
        qt_argv = [a for a in sys.argv if not a.startswith("--app=")]
        app = QApplication(qt_argv)
        app.setApplicationName(__app_name__)
        app.setOrganizationName("Shroudbyte")
        app.setDesktopFileName(f"shroudbyte-{os.getpid()}")

        # Apply theme palette for dialogs and system widgets
        from PyQt6.QtGui import QPalette
        from . import style

        dark = _settings.get("dark_mode", True)
        style.set_dark_mode(dark)

        palette = QPalette()
        if dark:
            palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(238, 238, 238))
            palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(43, 43, 43))
            palette.setColor(QPalette.ColorRole.Text, QColor(238, 238, 238))
            palette.setColor(QPalette.ColorRole.Button, QColor(43, 43, 43))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(238, 238, 238))
        else:
            palette.setColor(QPalette.ColorRole.Window, QColor(240, 238, 235))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(44, 37, 32))
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(247, 245, 242))
            palette.setColor(QPalette.ColorRole.Text, QColor(44, 37, 32))
            palette.setColor(QPalette.ColorRole.Button, QColor(247, 245, 242))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(44, 37, 32))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(41, 121, 255))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Link, QColor(41, 121, 255))
        app.setPalette(palette)

        if app_url:
            # PWA app mode — minimal window, no tabs, no URL bar
            from .appwindow import AppWindow
            window = AppWindow(app_url, dns_proxy=_proxy_instance)
            window.show()
        else:
            # If the previous launch left a running marker behind, it crashed
            # or was force-killed. Ask the user before silently restoring
            # whatever broken state caused the crash.
            _crashed_last_time = _crashhandler.was_previous_run_crashed()
            _open_log_after = False
            if _crashed_last_time:
                choice = _crashhandler.prompt_after_unclean_shutdown()
                if choice == "fresh":
                    from . import storage as _storage_mod
                    _storage_mod.clear_session()
                elif choice == "viewlog":
                    _open_log_after = True
            _crashhandler.mark_session_started()

            # Normal browser
            window = MainWindow(dns_proxy=_proxy_instance)
            if _open_log_after:
                from PyQt6.QtCore import QUrl as _QUrl
                from PyQt6.QtGui import QDesktopServices as _QDS
                _QDS.openUrl(_QUrl.fromLocalFile(str(_crashhandler.CRASH_LOG)))
            _mode = getattr(window, "_restore_window_state_mode", "normal")
            if _mode == "maximized":
                window.showMaximized()
            elif _mode == "fullscreen":
                window.showFullScreen()
            else:
                window.show()

            # Kill the splash now that the main window is visible.
            if splash_proc is not None:
                splash_proc.terminate()
                splash_proc.wait()
                splash_proc = None

        # Defer keyring migration until after the window is shown
        from PyQt6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, _deferred_dns_secret_migration)

        ret = app.exec()

        # Shut down the DNS proxy if it was running.
        if _proxy_instance is not None:
            _proxy_instance.stop()

        # Clean exit — remove the running marker so the next launch knows
        # the previous run finished gracefully.
        if not app_url:
            _crashhandler.mark_session_ended()

        sys.exit(ret)

    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        # The global excepthook should handle this, but as a safety net
        # re-invoke it explicitly in case something went wrong.
        _crashhandler._excepthook(*sys.exc_info())
        sys.exit(1)
    finally:
        # Make sure the splash doesn't linger if we crash during startup.
        if splash_proc is not None:
            splash_proc.terminate()
            splash_proc.wait()


if __name__ == "__main__":
    main()
