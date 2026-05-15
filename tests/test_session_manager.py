"""Tests for browser.session_manager — named session save/load/delete."""

import time

from browser import session_manager


class TestSessionManager:
    def test_save_and_load_round_trip(self, tmp_data_dir):
        tabs = [
            {"url": "https://a.com", "title": "A"},
            {"url": "https://b.com", "title": "B"},
        ]
        session_manager.save_named_session("work", tabs)
        assert session_manager.load_named_session("work") == tabs

    def test_load_missing_returns_empty(self, tmp_data_dir):
        assert session_manager.load_named_session("nope") == []

    def test_list_includes_metadata(self, tmp_data_dir):
        session_manager.save_named_session("a", [{"url": "x"}])
        session_manager.save_named_session("b", [{"url": "y"}, {"url": "z"}])
        listed = session_manager.list_sessions()
        names = {s["name"]: s for s in listed}
        assert names["a"]["tab_count"] == 1
        assert names["b"]["tab_count"] == 2
        for s in listed:
            assert s["updated_at"] > 0
            assert s["created_at"] > 0

    def test_list_sorted_most_recent_first(self, tmp_data_dir, monkeypatch):
        # Force distinct timestamps so sort order is unambiguous.
        # Use a generator that walks forward by 1s per call so every
        # call to time.time() returns a strictly-increasing value.
        counter = iter(range(1000, 2000))
        monkeypatch.setattr(time, "time", lambda: float(next(counter)))
        session_manager.save_named_session("old", [])
        session_manager.save_named_session("new", [])
        listed = session_manager.list_sessions()
        assert [s["name"] for s in listed] == ["new", "old"]

    def test_overwrite_preserves_created_at(self, tmp_data_dir, monkeypatch):
        counter = iter(range(1000, 2000))
        monkeypatch.setattr(time, "time", lambda: float(next(counter)))
        session_manager.save_named_session("s", [{"url": "v1"}])
        first_created = session_manager.list_sessions()[0]["created_at"]
        session_manager.save_named_session("s", [{"url": "v2"}])
        [info] = session_manager.list_sessions()
        # The first save's created_at must survive the overwrite.
        assert info["created_at"] == first_created
        assert info["updated_at"] > info["created_at"]
        assert session_manager.load_named_session("s") == [{"url": "v2"}]

    def test_delete_removes(self, tmp_data_dir):
        session_manager.save_named_session("doomed", [{"url": "x"}])
        session_manager.delete_session("doomed")
        assert session_manager.list_sessions() == []
        assert session_manager.load_named_session("doomed") == []

    def test_delete_missing_is_safe(self, tmp_data_dir):
        # Must not raise.
        session_manager.delete_session("nonexistent")
