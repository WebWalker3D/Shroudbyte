"""Screen Time — per-domain browsing time tracker.

Tracks how long the user spends on each domain (not full URLs) per day.
Domain-level only, off in private mode, opt-in via settings.
"""

import time

from PyQt6.QtCore import QObject, QTimer

from . import storage


_SAVE_INTERVAL = 30  # flush to disk every 30 seconds


class ScreenTimeTracker(QObject):
    """Accumulates active browsing time per domain."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = False
        self._private = False
        self._current_domain = ""
        self._tick_count = 0  # seconds on current domain since last flush
        self._pending: dict[str, int] = {}  # domain -> seconds to flush

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self, enabled: bool, private: bool):
        self._enabled = enabled
        self._private = private
        if enabled and not private:
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self._flush()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if enabled and not self._private:
            self._timer.start()
        else:
            self._timer.stop()
            self._flush()

    def set_domain(self, domain: str):
        """Called when the active tab's domain changes."""
        if not self._enabled or self._private:
            return
        if not domain:
            return
        clean = domain.lower().removeprefix("www.")
        if clean == self._current_domain:
            return
        # Flush accumulated time for the old domain
        if self._current_domain and self._tick_count > 0:
            self._pending[self._current_domain] = (
                self._pending.get(self._current_domain, 0) + self._tick_count
            )
            self._tick_count = 0
        self._current_domain = clean

    def _tick(self):
        if not self._current_domain:
            return
        self._tick_count += 1
        # Periodic flush to disk
        if self._tick_count >= _SAVE_INTERVAL:
            self._pending[self._current_domain] = (
                self._pending.get(self._current_domain, 0) + self._tick_count
            )
            self._tick_count = 0
            self._flush()

    def _flush(self):
        if not self._pending:
            return
        today = time.strftime("%Y-%m-%d")
        data = storage.load_screen_time()
        for domain, secs in self._pending.items():
            if not domain:
                continue
            if domain not in data:
                data[domain] = {}
            data[domain][today] = data[domain].get(today, 0) + secs
        storage.save_screen_time(data)
        self._pending.clear()

    def get_today_domain_time(self, domain: str) -> int:
        """Return seconds spent on a domain today (for status bar display)."""
        self._flush()
        today = time.strftime("%Y-%m-%d")
        clean = domain.lower().removeprefix("www.")
        data = storage.load_screen_time()
        return data.get(clean, {}).get(today, 0)
