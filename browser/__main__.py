"""Entry point for Shroudbyte."""

import ctypes
import ctypes.util
import fcntl
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

# Migrate legacy plaintext secrets to keyring on first launch
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

# Keep a module-level reference so the lock file stays open for the process lifetime.
_lock_file = None


def _acquire_single_instance_lock():
    """Try to acquire an exclusive lock. Returns True if we are the only instance."""
    global _lock_file
    lock_path = _storage.DATA_DIR / "shroudbyte.lock"
    _storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
        return True
    except OSError:
        _lock_file.close()
        _lock_file = None
        return False


def release_single_instance_lock():
    """Release the instance lock so a restart can re-acquire it."""
    global _lock_file
    if _lock_file is not None:
        fcntl.flock(_lock_file, fcntl.LOCK_UN)
        _lock_file.close()
        _lock_file = None


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


def main():
    if not _acquire_single_instance_lock():
        print("Shroudbyte is already running.", file=sys.stderr)
        sys.exit(0)

    splash_proc = None
    try:
        # Launch splash in a separate process — it appears instantly while we
        # do the heavy Qt WebEngine initialisation in this process.
        splash_proc = _launch_splash()

        app = QApplication(sys.argv)
        app.setApplicationName(__app_name__)
        app.setOrganizationName("Shroudbyte")
        app.setDesktopFileName("shroudbyte")

        # Dark palette for dialogs and system widgets
        from PyQt6.QtGui import QPalette

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

        window = MainWindow(dns_proxy=_proxy_instance)
        window.show()

        # Kill the splash now that the main window is visible.
        splash_proc.terminate()
        splash_proc.wait()
        splash_proc = None

        ret = app.exec()

        # Shut down the DNS proxy if it was running.
        if _proxy_instance is not None:
            _proxy_instance.stop()

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
