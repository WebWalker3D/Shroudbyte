"""Global crash handler for Blade Browser.

Catches unhandled exceptions, logs them to a crash file, and shows a
dialog so the user can see what went wrong instead of a silent exit.
"""

import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import storage

CRASH_LOG = storage.DATA_DIR / "crash.log"

logger = logging.getLogger("blade.crash")

# Maximum crash log size before it gets rotated (512 KB).
_MAX_LOG_BYTES = 512 * 1024


def _rotate_log_if_needed():
    """Keep the crash log from growing unbounded."""
    try:
        if CRASH_LOG.exists() and CRASH_LOG.stat().st_size > _MAX_LOG_BYTES:
            backup = CRASH_LOG.with_suffix(".log.old")
            CRASH_LOG.replace(backup)
    except OSError:
        pass


def _format_crash(exc_type, exc_value, exc_tb):
    """Return a formatted crash report string."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_text = "".join(tb_lines)
    return (
        f"--- Crash at {timestamp} ---\n"
        f"{tb_text}"
        f"---\n\n"
    )


def _write_crash_log(report: str):
    """Append the crash report to the log file."""
    try:
        _rotate_log_if_needed()
        storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(report)
    except OSError:
        pass  # Last resort — nothing we can do if logging itself fails.


def _show_crash_dialog(report: str):
    """Show a Qt dialog with the crash details (best-effort)."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox, QTextEdit
        from PyQt6.QtCore import Qt

        # If there's no QApplication yet, we can't show a dialog.
        app = QApplication.instance()
        if app is None:
            return

        box = QMessageBox()
        box.setWindowTitle("Blade Browser — Crash Report")
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText("Blade Browser encountered an unexpected error and needs to close.")
        box.setInformativeText(f"Details have been saved to:\n{CRASH_LOG}")
        box.setDetailedText(report)
        box.setStandardButtons(QMessageBox.StandardButton.Close)

        # Widen the details area so tracebacks are readable.
        box.setStyleSheet("QTextEdit { min-width: 600px; min-height: 300px; }")

        box.exec()
    except Exception:
        # If the dialog itself fails, just print to stderr as a fallback.
        pass


def _excepthook(exc_type, exc_value, exc_tb):
    """Global exception hook — replaces sys.excepthook."""
    # Ignore KeyboardInterrupt so Ctrl+C still works normally.
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    report = _format_crash(exc_type, exc_value, exc_tb)

    # Always print to stderr in case the log/dialog fail.
    sys.stderr.write(report)

    _write_crash_log(report)
    _show_crash_dialog(report)


def install():
    """Install the global crash handler.

    Call this as early as possible in the application startup.
    Sets up:
      - sys.excepthook for unhandled exceptions in the main thread
      - logging to the crash log file
    """
    sys.excepthook = _excepthook

    # Also set up basic logging so other modules can use logger.error()
    # and have it land in the crash log.
    storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_log_if_needed()
    file_handler = logging.FileHandler(CRASH_LOG, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    logging.root.addHandler(file_handler)
    logging.root.setLevel(logging.WARNING)
