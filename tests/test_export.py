"""Tests for browser.export — encrypted browser state export/import."""

import pytest

from browser import storage
from browser.export import export_state, import_state, EXPORT_COLLECTIONS


class TestExportImportRoundTrip:

    def test_basic_round_trip(self):
        """Export and re-import should preserve data."""
        storage.save_bookmarks([
            {"url": "https://example.com", "title": "Example"},
        ])
        storage.save_settings({"search_engine": "https://ddg.gg/?q={}"})

        blob = export_state("secret123")
        storage.invalidate_cache()
        # Clear existing data
        storage.save_bookmarks([])
        storage.save_settings({})

        result = import_state(blob, "secret123", merge=False)
        assert "bookmarks" in result
        assert "settings" in result

        bm = storage.load_bookmarks()
        assert len(bm) == 1
        assert bm[0]["url"] == "https://example.com"

    def test_round_trip_all_collections(self):
        """All exportable collections survive a round trip."""
        storage.save_bookmarks([{"url": "https://a.com", "title": "A"}])
        storage.save_cookie_whitelist(["example.com"])
        storage.save_watches([{"url": "https://w.com", "title": "W"}])

        blob = export_state("pw")
        storage.invalidate_cache()
        storage.save_bookmarks([])
        storage.save_cookie_whitelist([])
        storage.save_watches([])

        result = import_state(blob, "pw", merge=False)
        assert storage.load_bookmarks()[0]["url"] == "https://a.com"
        assert "example.com" in storage.load_cookie_whitelist()
        assert storage.load_watches()[0]["url"] == "https://w.com"


class TestWrongPassword:

    def test_wrong_password_raises(self):
        """Import with wrong password must fail."""
        blob = export_state("correct-password")
        with pytest.raises(Exception):
            import_state(blob, "wrong-password")


class TestInvalidMagic:

    def test_invalid_magic_raises_value_error(self):
        """Data that doesn't start with SHROUD_EXPORT is rejected."""
        with pytest.raises(ValueError, match="Not a valid Shroudbyte export file"):
            import_state(b"NOT_A_VALID_EXPORT_FILE", "password")

    def test_empty_data_raises(self):
        with pytest.raises(ValueError, match="Not a valid Shroudbyte export file"):
            import_state(b"", "password")


class TestMergeBehavior:

    def test_merge_preserves_existing_bookmarks(self):
        """Merging should keep existing bookmarks and add new ones."""
        storage.save_bookmarks([
            {"url": "https://existing.com", "title": "Existing"},
        ])

        # Export some bookmarks from a different state
        storage.invalidate_cache()
        storage.save_bookmarks([
            {"url": "https://new.com", "title": "New"},
            {"url": "https://existing.com", "title": "Existing Duplicate"},
        ])
        blob = export_state("pw", collections=["bookmarks"])

        # Reset to original state
        storage.invalidate_cache()
        storage.save_bookmarks([
            {"url": "https://existing.com", "title": "Existing"},
        ])

        result = import_state(blob, "pw", collections=["bookmarks"], merge=True)
        bm = storage.load_bookmarks()
        urls = [b["url"] for b in bm]
        assert "https://existing.com" in urls
        assert "https://new.com" in urls
        # The existing one should not be duplicated
        assert urls.count("https://existing.com") == 1

    def test_merge_dict_collections(self):
        """Merging dict collections should update keys."""
        storage.save_permissions({"example.com": {"camera": "allow"}})

        # Export different permissions
        storage.invalidate_cache()
        storage.save_permissions({"other.com": {"mic": "deny"}})
        blob = export_state("pw", collections=["permissions"])

        # Restore original
        storage.invalidate_cache()
        storage.save_permissions({"example.com": {"camera": "allow"}})

        import_state(blob, "pw", collections=["permissions"], merge=True)
        perms = storage.load_permissions()
        assert "example.com" in perms
        assert "other.com" in perms

    def test_merge_plain_list_items(self):
        """Merge of plain (non-dict) list items avoids duplicates."""
        storage.save_cookie_whitelist(["existing.com"])

        storage.invalidate_cache()
        storage.save_cookie_whitelist(["existing.com", "new.com"])
        blob = export_state("pw", collections=["cookie_whitelist"])

        storage.invalidate_cache()
        storage.save_cookie_whitelist(["existing.com"])

        import_state(blob, "pw", collections=["cookie_whitelist"], merge=True)
        wl = storage.load_cookie_whitelist()
        assert "existing.com" in wl
        assert "new.com" in wl
        assert wl.count("existing.com") == 1


class TestOverwriteBehavior:

    def test_overwrite_replaces_data(self):
        """merge=False should replace existing data entirely."""
        storage.save_bookmarks([
            {"url": "https://old.com", "title": "Old"},
        ])

        # Export different bookmarks
        storage.invalidate_cache()
        storage.save_bookmarks([
            {"url": "https://new.com", "title": "New"},
        ])
        blob = export_state("pw", collections=["bookmarks"])

        # Restore original
        storage.invalidate_cache()
        storage.save_bookmarks([
            {"url": "https://old.com", "title": "Old"},
        ])

        import_state(blob, "pw", collections=["bookmarks"], merge=False)
        bm = storage.load_bookmarks()
        urls = [b["url"] for b in bm]
        assert "https://new.com" in urls
        assert "https://old.com" not in urls


class TestSelectiveCollections:

    def test_export_only_bookmarks(self):
        """Selective export should only include requested collections."""
        storage.save_bookmarks([{"url": "https://a.com", "title": "A"}])
        storage.save_cookie_whitelist(["b.com"])

        blob = export_state("pw", collections=["bookmarks"])

        storage.invalidate_cache()
        storage.save_bookmarks([])
        storage.save_cookie_whitelist([])

        result = import_state(blob, "pw", merge=False)
        assert "bookmarks" in result
        assert "cookie_whitelist" not in result
        assert len(storage.load_bookmarks()) == 1
        assert len(storage.load_cookie_whitelist()) == 0

    def test_import_only_selected_collections(self):
        """Import can restrict which collections are applied."""
        storage.save_bookmarks([{"url": "https://a.com", "title": "A"}])
        storage.save_cookie_whitelist(["b.com"])

        blob = export_state("pw")  # exports everything

        storage.invalidate_cache()
        storage.save_bookmarks([])
        storage.save_cookie_whitelist([])

        result = import_state(blob, "pw", collections=["bookmarks"], merge=False)
        assert "bookmarks" in result
        assert "cookie_whitelist" not in result
        assert len(storage.load_bookmarks()) == 1
        assert len(storage.load_cookie_whitelist()) == 0
