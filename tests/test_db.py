"""Tests for browser.db — SQLite backend for history, screen_time, scroll_positions, form_drafts."""

import json
import time
from pathlib import Path

import pytest

from browser.db import Database


@pytest.fixture
def db(tmp_path):
    """Create a Database with an explicit temp path."""
    d = Database(db_path=tmp_path / "test.db")
    yield d
    d.close()


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class TestHistory:
    def test_add_and_load(self, db):
        db.add_history_entry("A", "https://a.com")
        db.add_history_entry("B", "https://b.com")
        history = db.load_history()
        assert len(history) == 2
        # Newest first
        assert history[0]["url"] == "https://b.com"
        assert history[1]["url"] == "https://a.com"

    def test_clear(self, db):
        db.add_history_entry("A", "https://a.com")
        db.clear_history()
        assert db.load_history() == []

    def test_5000_cap(self, db):
        for i in range(5010):
            db.add_history_entry(f"Page {i}", f"https://example.com/{i}")
        history = db.load_history()
        assert len(history) == 5000

    def test_newest_first(self, db):
        db.add_history_entry("First", "https://first.com")
        db.add_history_entry("Second", "https://second.com")
        db.add_history_entry("Third", "https://third.com")
        history = db.load_history()
        assert history[0]["title"] == "Third"
        assert history[-1]["title"] == "First"


# ---------------------------------------------------------------------------
# URL suggestions
# ---------------------------------------------------------------------------

class TestURLSuggestions:
    def test_dedup_by_url(self, db):
        db.add_history_entry("A", "https://a.com")
        db.add_history_entry("A", "https://a.com")
        db.add_history_entry("B", "https://b.com")
        suggestions = db.get_url_suggestions()
        urls = [s[0] for s in suggestions]
        assert len(set(urls)) == len(urls)

    def test_frequency_sorting(self, db):
        for _ in range(5):
            db.add_history_entry("Popular", "https://popular.com")
        db.add_history_entry("Rare", "https://rare.com")
        suggestions = db.get_url_suggestions()
        assert suggestions[0][0] == "https://popular.com"
        assert suggestions[0][2] == 5  # frequency

    def test_bookmark_merge(self, db, tmp_data_dir):
        from browser import storage
        storage.add_bookmark("BM", "https://bookmarked.com")
        suggestions = db.get_url_suggestions()
        urls = [s[0] for s in suggestions]
        assert "https://bookmarked.com" in urls
        # Bookmark-only entry has frequency 0
        bm_entry = [s for s in suggestions if s[0] == "https://bookmarked.com"][0]
        assert bm_entry[2] == 0


# ---------------------------------------------------------------------------
# Screen time
# ---------------------------------------------------------------------------

class TestScreenTime:
    def test_add_and_load(self, db):
        db.add_screen_time("example.com", "2025-01-01", 120)
        data = db.load_screen_time()
        assert data["example.com"]["2025-01-01"] == 120

    def test_accumulate_same_domain_date(self, db):
        db.add_screen_time("example.com", "2025-01-01", 60)
        db.add_screen_time("example.com", "2025-01-01", 90)
        data = db.load_screen_time()
        assert data["example.com"]["2025-01-01"] == 150

    def test_batch_add(self, db):
        db.add_screen_time_batch({"a.com": 10, "b.com": 20}, "2025-01-01")
        data = db.load_screen_time()
        assert data["a.com"]["2025-01-01"] == 10
        assert data["b.com"]["2025-01-01"] == 20

    def test_clear(self, db):
        db.add_screen_time("example.com", "2025-01-01", 100)
        db.clear_screen_time()
        assert db.load_screen_time() == {}


# ---------------------------------------------------------------------------
# Scroll positions
# ---------------------------------------------------------------------------

class TestScrollPositions:
    def test_set_and_get(self, db):
        db.set_scroll_position("https://a.com", 0.75)
        assert db.get_scroll_position("https://a.com") == 0.75

    def test_get_missing_returns_zero(self, db):
        assert db.get_scroll_position("https://missing.com") == 0.0

    def test_near_zero_deletes(self, db):
        db.set_scroll_position("https://a.com", 0.5)
        db.set_scroll_position("https://a.com", 0.005)
        assert db.get_scroll_position("https://a.com") == 0.0

    def test_lru_eviction_beyond_2000(self, db):
        # Insert 2005 entries
        for i in range(2005):
            db.set_scroll_position(f"https://example.com/{i}", 0.5)
        # Count remaining
        conn = db._connect()
        count = conn.execute("SELECT COUNT(*) as c FROM scroll_positions").fetchone()["c"]
        assert count == 2000


# ---------------------------------------------------------------------------
# Form drafts
# ---------------------------------------------------------------------------

class TestFormDrafts:
    def test_save_and_get(self, db):
        fields = {"name": "Alice", "email": "alice@example.com"}
        db.save_form_draft("https://form.com", fields, timestamp=1000.0)
        draft = db.get_form_draft("https://form.com")
        assert draft is not None
        assert draft["fields"] == fields
        assert draft["saved"] == 1000.0

    def test_get_missing(self, db):
        assert db.get_form_draft("https://missing.com") is None

    def test_remove(self, db):
        db.save_form_draft("https://form.com", {"a": "1"})
        db.remove_form_draft("https://form.com")
        assert db.get_form_draft("https://form.com") is None

    def test_lru_eviction_beyond_200(self, db):
        for i in range(205):
            db.save_form_draft(f"https://example.com/{i}", {"i": i})
        conn = db._connect()
        count = conn.execute("SELECT COUNT(*) as c FROM form_drafts").fetchone()["c"]
        assert count == 200


# ---------------------------------------------------------------------------
# JSON migration
# ---------------------------------------------------------------------------

class TestMigration:
    def test_migrate_history(self, tmp_data_dir, tmp_path):
        # Create legacy JSON file
        legacy = [
            {"url": "https://old.com", "title": "Old Page", "visited": 1700000000.0},
        ]
        (tmp_data_dir / "history.json").write_text(json.dumps(legacy))

        db = Database(db_path=tmp_path / "mig.db")
        db.migrate_from_json()

        history = db.load_history()
        assert len(history) == 1
        assert history[0]["url"] == "https://old.com"
        assert history[0]["title"] == "Old Page"

        # Original file renamed
        assert not (tmp_data_dir / "history.json").exists()
        assert (tmp_data_dir / "history.json.migrated").exists()
        db.close()

    def test_migrate_screen_time(self, tmp_data_dir, tmp_path):
        legacy = {"example.com": {"2025-01-01": 300}}
        (tmp_data_dir / "screen_time.json").write_text(json.dumps(legacy))

        db = Database(db_path=tmp_path / "mig.db")
        db.migrate_from_json()

        data = db.load_screen_time()
        assert data["example.com"]["2025-01-01"] == 300
        assert not (tmp_data_dir / "screen_time.json").exists()
        assert (tmp_data_dir / "screen_time.json.migrated").exists()
        db.close()

    def test_migrate_scroll_positions(self, tmp_data_dir, tmp_path):
        legacy = {"https://page.com": 0.42}
        (tmp_data_dir / "scroll_positions.json").write_text(json.dumps(legacy))

        db = Database(db_path=tmp_path / "mig.db")
        db.migrate_from_json()

        assert db.get_scroll_position("https://page.com") == 0.42
        assert not (tmp_data_dir / "scroll_positions.json").exists()
        db.close()

    def test_migrate_form_drafts(self, tmp_data_dir, tmp_path):
        legacy = {
            "https://form.com": {
                "fields": {"name": "Bob"},
                "saved": 1700000000.0,
            }
        }
        (tmp_data_dir / "form_drafts.json").write_text(json.dumps(legacy))

        db = Database(db_path=tmp_path / "mig.db")
        db.migrate_from_json()

        draft = db.get_form_draft("https://form.com")
        assert draft is not None
        assert draft["fields"]["name"] == "Bob"
        assert not (tmp_data_dir / "form_drafts.json").exists()
        db.close()
