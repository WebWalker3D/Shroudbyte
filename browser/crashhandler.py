"""Global crash handler for Shroudbyte.

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
RUNNING_MARKER = storage.DATA_DIR / ".running"

logger = logging.getLogger("shroudbyte.crash")

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
    """Show a Qt dialog with the crash details (best-effort).

    Gives the user explicit, opt-in actions:
      * Copy the report to the clipboard (so they can paste it into an
        issue tracker themselves — Shroudbyte never uploads on its own)
      * Open the crash log directory
    """
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        # If there's no QApplication yet, we can't show a dialog.
        app = QApplication.instance()
        if app is None:
            return

        box = QMessageBox()
        box.setWindowTitle("Shroudbyte — Crash Report")
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText("Shroudbyte encountered an unexpected error and needs to close.")
        box.setInformativeText(
            f"Details have been saved to:\n{CRASH_LOG}\n\n"
            "Shroudbyte never uploads crash data. If you'd like to share "
            "this report, use 'Copy to clipboard' and paste it into a "
            "GitHub issue yourself."
        )
        box.setDetailedText(report)
        close_btn = box.addButton(QMessageBox.StandardButton.Close)
        copy_btn = box.addButton(
            "Copy to clipboard", QMessageBox.ButtonRole.ActionRole
        )
        open_btn = box.addButton(
            "Open log folder", QMessageBox.ButtonRole.ActionRole
        )
        box.setDefaultButton(close_btn)

        # Widen the details area so tracebacks are readable.
        box.setStyleSheet("QTextEdit { min-width: 600px; min-height: 300px; }")

        box.exec()
        clicked = box.clickedButton()
        if clicked is copy_btn:
            cb = QApplication.clipboard()
            if cb is not None:
                cb.setText(report)
        elif clicked is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(CRASH_LOG.parent)))
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


# ---------------------------------------------------------------------------
# Ungraceful-shutdown detection
#
# A simple "running marker" file: written at startup, removed on a clean
# exit. If it's still present at the next startup, the previous run died
# without going through closeEvent — i.e. crashed or was force-killed.
# ---------------------------------------------------------------------------

def was_previous_run_crashed() -> bool:
    """True iff a running marker from a previous launch is still present.

    Must be called BEFORE :func:`mark_session_started` so the check looks
    at the previous run's marker rather than the current one's.
    """
    return RUNNING_MARKER.exists()


def mark_session_started():
    """Drop a marker file so the next launch can detect an unclean shutdown."""
    try:
        storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
        RUNNING_MARKER.write_text(str(int(datetime.now(timezone.utc).timestamp())))
    except OSError as e:
        logger.warning("Could not write running marker: %s", e)


def mark_session_ended():
    """Remove the marker file on a clean shutdown."""
    try:
        if RUNNING_MARKER.exists():
            RUNNING_MARKER.unlink()
    except OSError as e:
        logger.warning("Could not remove running marker: %s", e)


def prompt_after_unclean_shutdown() -> str:
    """Show a recovery dialog after detecting a prior crash.

    Returns one of:
      - "restore"   — proceed with normal session restore (default)
      - "fresh"     — clear the saved session so the user starts blank
      - "viewlog"   — same as restore, but the caller should open the log
    """
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return "restore"

        box = QMessageBox()
        box.setWindowTitle("Shroudbyte — Recover from crash?")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "Shroudbyte didn't close cleanly last time."
        )
        box.setInformativeText(
            "Restore your previous tabs, or start with a fresh session?\n\n"
            f"Crash log: {CRASH_LOG}"
        )
        restore_btn = box.addButton(
            "Restore previous tabs", QMessageBox.ButtonRole.AcceptRole
        )
        fresh_btn = box.addButton(
            "Start fresh", QMessageBox.ButtonRole.DestructiveRole
        )
        view_btn = box.addButton(
            "View crash log", QMessageBox.ButtonRole.ActionRole
        )
        box.setDefaultButton(restore_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is fresh_btn:
            return "fresh"
        if clicked is view_btn:
            return "viewlog"
        return "restore"
    except Exception as e:
        logger.error("Crash recovery dialog failed: %s", e, exc_info=True)
        return "restore"
