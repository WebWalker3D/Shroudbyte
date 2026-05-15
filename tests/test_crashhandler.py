"""Tests for browser.crashhandler — running marker / crash detection."""

from browser import crashhandler


def _reload_paths(tmp_data_dir, monkeypatch):
    """crashhandler captures DATA_DIR at import time; redirect the paths."""
    monkeypatch.setattr(
        crashhandler, "CRASH_LOG", tmp_data_dir / "crash.log"
    )
    monkeypatch.setattr(
        crashhandler, "RUNNING_MARKER", tmp_data_dir / ".running"
    )


class TestRunningMarker:
    def test_fresh_install_is_not_crashed(self, tmp_data_dir, monkeypatch):
        _reload_paths(tmp_data_dir, monkeypatch)
        assert crashhandler.was_previous_run_crashed() is False

    def test_marker_persists_and_signals_crash(self, tmp_data_dir, monkeypatch):
        _reload_paths(tmp_data_dir, monkeypatch)
        crashhandler.mark_session_started()
        # Simulate process death by NOT calling mark_session_ended.
        assert crashhandler.was_previous_run_crashed() is True

    def test_clean_shutdown_clears_marker(self, tmp_data_dir, monkeypatch):
        _reload_paths(tmp_data_dir, monkeypatch)
        crashhandler.mark_session_started()
        crashhandler.mark_session_ended()
        assert crashhandler.was_previous_run_crashed() is False

    def test_repeated_clean_end_is_safe(self, tmp_data_dir, monkeypatch):
        _reload_paths(tmp_data_dir, monkeypatch)
        # Should not raise even if marker doesn't exist.
        crashhandler.mark_session_ended()
        crashhandler.mark_session_ended()
