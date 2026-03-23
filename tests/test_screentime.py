"""Tests for browser.screentime — domain time tracking logic.

ScreenTimeTracker uses QTimer (PyQt6), so we test the pure-logic methods
by manually driving _tick / _flush / set_domain rather than instantiating
the full QObject.  If PyQt6 is unavailable the tests are skipped.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

try:
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from browser.screentime import ScreenTimeTracker
    HAS_QT = True
except Exception:
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PyQt6 not available")


@pytest.fixture
def tracker():
    """Create a ScreenTimeTracker with the timer started (enabled, not private)."""
    t = ScreenTimeTracker()
    t._enabled = True
    t._private = False
    return t


class TestSetDomain:
    """set_domain() should accumulate time for the old domain."""

    def test_switching_domain_accumulates_time(self, tracker):
        tracker.set_domain("example.com")
        # Simulate 5 ticks on example.com
        for _ in range(5):
            tracker._tick()

        # Switch domain — old ticks should move to _pending
        tracker.set_domain("other.com")

        assert tracker._pending.get("example.com", 0) == 5
        assert tracker._current_domain == "other.com"
        assert tracker._tick_count == 0

    def test_set_domain_strips_www(self, tracker):
        tracker.set_domain("www.example.com")
        assert tracker._current_domain == "example.com"

    def test_set_domain_lowercases(self, tracker):
        tracker.set_domain("Example.COM")
        assert tracker._current_domain == "example.com"

    def test_set_domain_noop_when_disabled(self, tracker):
        tracker._enabled = False
        tracker.set_domain("example.com")
        assert tracker._current_domain == ""

    def test_set_domain_noop_when_private(self, tracker):
        tracker._private = True
        tracker.set_domain("example.com")
        assert tracker._current_domain == ""

    def test_set_domain_ignores_empty(self, tracker):
        tracker.set_domain("")
        assert tracker._current_domain == ""

    def test_set_domain_same_domain_noop(self, tracker):
        tracker.set_domain("example.com")
        tracker._tick_count = 10
        # Setting the same domain again should not flush
        tracker.set_domain("example.com")
        assert tracker._tick_count == 10
        assert "example.com" not in tracker._pending


class TestFlush:
    """_flush() writes pending times to the database."""

    def test_flush_writes_to_db(self, tracker, tmp_data_dir):
        tracker._pending = {"example.com": 120, "other.com": 60}

        mock_db = MagicMock()
        with patch("browser.db.get_db", return_value=mock_db):
            tracker._flush()

        mock_db.add_screen_time_batch.assert_called_once()
        args = mock_db.add_screen_time_batch.call_args
        domain_dict = args[0][0]
        assert domain_dict["example.com"] == 120
        assert domain_dict["other.com"] == 60

        # _pending should be cleared after flush
        assert tracker._pending == {}

    def test_flush_noop_when_empty(self, tracker):
        """Flush with no pending data should not call the DB."""
        mock_db = MagicMock()
        with patch("browser.db.get_db", return_value=mock_db):
            tracker._flush()
        mock_db.add_screen_time_batch.assert_not_called()


class TestSetEnabled:
    """set_enabled(False) should stop the timer and flush."""

    def test_disable_flushes_pending(self, tracker):
        tracker.set_domain("example.com")
        for _ in range(3):
            tracker._tick()

        # Accumulate into pending by switching domain
        tracker.set_domain("other.com")
        assert tracker._pending.get("example.com") == 3

        mock_db = MagicMock()
        with patch("browser.db.get_db", return_value=mock_db):
            tracker.set_enabled(False)

        assert tracker._enabled is False
        # Timer should be stopped
        assert not tracker._timer.isActive()
        # Pending should have been flushed
        mock_db.add_screen_time_batch.assert_called_once()

    def test_enable_starts_timer(self, tracker):
        tracker._private = False
        tracker.set_enabled(True)
        assert tracker._enabled is True
        assert tracker._timer.isActive()
        tracker._timer.stop()  # cleanup
