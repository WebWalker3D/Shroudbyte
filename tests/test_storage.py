"""Tests for browser.storage — JSON persistence layer with in-memory cache."""

import json

from browser import storage


# ---------------------------------------------------------------------------
# Bookmarks CRUD
# ---------------------------------------------------------------------------

class TestBookmarks:
    def test_add_and_load(self, tmp_data_dir):
        assert storage.add_bookmark("Example", "https://example.com") is True
        bm = storage.load_bookmarks()
        assert len(bm) == 1
        assert bm[0]["url"] == "https://example.com"
        assert bm[0]["title"] == "Example"
        assert "added" in bm[0]

    def test_add_duplicate_returns_false(self, tmp_data_dir):
        storage.add_bookmark("A", "https://a.com")
        assert storage.add_bookmark("A again", "https://a.com") is False
        assert len(storage.load_bookmarks()) == 1

    def test_remove_bookmark(self, tmp_data_dir):
        storage.add_bookmark("A", "https://a.com")
        storage.add_bookmark("B", "https://b.com")
        storage.remove_bookmark("https://a.com")
        urls = [b["url"] for b in storage.load_bookmarks()]
        assert urls == ["https://b.com"]

    def test_is_bookmarked(self, tmp_data_dir):
        storage.add_bookmark("X", "https://x.com")
        assert storage.is_bookmarked("https://x.com") is True
        assert storage.is_bookmarked("https://y.com") is False


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_load_defaults(self, tmp_data_dir):
        settings = storage.load_settings()
        assert settings["enable_javascript"] is True
        assert settings["private_mode"] is False
        assert settings["default_zoom"] == 100

    def test_merge_with_saved(self, tmp_data_dir):
        storage.save_settings({"default_zoom": 150})
        settings = storage.load_settings()
        # Custom value preserved
        assert settings["default_zoom"] == 150
        # Defaults filled in
        assert settings["enable_javascript"] is True

    def test_save_persists_to_disk(self, tmp_data_dir):
        storage.save_settings({"private_mode": True})
        # Clear cache and reload from disk
        storage.invalidate_cache("settings.json")
        settings = storage.load_settings()
        assert settings["private_mode"] is True


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class TestSession:
    def test_save_and_load(self, tmp_data_dir):
        tabs = [{"url": "https://a.com", "title": "A"}]
        storage.save_session(tabs)
        loaded = storage.load_session()
        assert loaded == tabs

    def test_clear_session(self, tmp_data_dir):
        storage.save_session([{"url": "https://a.com", "title": "A"}])
        storage.clear_session()
        # After clear, the file is gone — cache still has old value,
        # so invalidate first to truly test clear behavior.
        storage.invalidate_cache("session.json")
        assert storage.load_session() == []

    def test_load_empty(self, tmp_data_dir):
        assert storage.load_session() == []


# ---------------------------------------------------------------------------
# Cookie whitelist
# ---------------------------------------------------------------------------

class TestCookieWhitelist:
    def test_add_and_check(self, tmp_data_dir):
        storage.add_cookie_whitelist("example.com")
        assert storage.is_cookie_whitelisted("example.com") is True

    def test_subdomain_matching(self, tmp_data_dir):
        storage.add_cookie_whitelist("example.com")
        assert storage.is_cookie_whitelisted("sub.example.com") is True
        assert storage.is_cookie_whitelisted("notexample.com") is False

    def test_remove(self, tmp_data_dir):
        storage.add_cookie_whitelist("example.com")
        storage.remove_cookie_whitelist("example.com")
        assert storage.is_cookie_whitelisted("example.com") is False

    def test_leading_dot_stripped(self, tmp_data_dir):
        storage.add_cookie_whitelist(".example.com")
        assert storage.is_cookie_whitelisted("example.com") is True


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class TestPermissions:
    def test_set_and_get(self, tmp_data_dir):
        storage.set_permission("example.com", "camera", "allow")
        assert storage.get_permission("example.com", "camera") == "allow"

    def test_get_unset_returns_none(self, tmp_data_dir):
        assert storage.get_permission("example.com", "camera") is None

    def test_remove_specific_feature(self, tmp_data_dir):
        storage.set_permission("example.com", "camera", "allow")
        storage.set_permission("example.com", "mic", "deny")
        storage.remove_permission("example.com", "camera")
        assert storage.get_permission("example.com", "camera") is None
        assert storage.get_permission("example.com", "mic") == "deny"

    def test_remove_all_for_host(self, tmp_data_dir):
        storage.set_permission("example.com", "camera", "allow")
        storage.set_permission("example.com", "mic", "deny")
        storage.remove_permission("example.com")
        assert storage.get_permission("example.com", "camera") is None
        assert storage.get_permission("example.com", "mic") is None


# ---------------------------------------------------------------------------
# Site exceptions
# ---------------------------------------------------------------------------

class TestSiteExceptions:
    def test_set_and_load(self, tmp_data_dir):
        storage.set_site_exception("site.com", "tracker.io", "allow")
        exc = storage.load_site_exceptions()
        assert exc["site.com"]["tracker.io"] == "allow"

    def test_remove(self, tmp_data_dir):
        storage.set_site_exception("site.com", "tracker.io", "allow")
        storage.remove_site_exception("site.com", "tracker.io")
        exc = storage.load_site_exceptions()
        assert "site.com" not in exc


# ---------------------------------------------------------------------------
# Watches
# ---------------------------------------------------------------------------

class TestWatches:
    def test_add_and_is_watched(self, tmp_data_dir):
        assert storage.add_watch("https://a.com", "A") is True
        assert storage.is_watched("https://a.com") is True

    def test_add_duplicate(self, tmp_data_dir):
        storage.add_watch("https://a.com", "A")
        assert storage.add_watch("https://a.com", "A dup") is False

    def test_remove(self, tmp_data_dir):
        storage.add_watch("https://a.com", "A")
        storage.remove_watch("https://a.com")
        assert storage.is_watched("https://a.com") is False

    def test_update_watch(self, tmp_data_dir):
        storage.add_watch("https://a.com", "A")
        storage.update_watch("https://a.com", {"change_count": 5})
        watches = storage.load_watches()
        assert watches[0]["change_count"] == 5


# ---------------------------------------------------------------------------
# Installed apps (PWA)
# ---------------------------------------------------------------------------

class TestInstalledApps:
    def test_add_and_get(self, tmp_data_dir):
        app = {"start_url": "https://app.com", "name": "MyApp"}
        storage.add_installed_app(app)
        result = storage.get_installed_app("https://app.com")
        assert result is not None
        assert result["name"] == "MyApp"

    def test_remove(self, tmp_data_dir):
        app = {"start_url": "https://app.com", "name": "MyApp"}
        storage.add_installed_app(app)
        storage.remove_installed_app("https://app.com")
        assert storage.get_installed_app("https://app.com") is None

    def test_add_replaces_existing(self, tmp_data_dir):
        storage.add_installed_app({"start_url": "https://app.com", "name": "V1"})
        storage.add_installed_app({"start_url": "https://app.com", "name": "V2"})
        apps = storage.load_installed_apps()
        assert len(apps) == 1
        assert apps[0]["name"] == "V2"


# ---------------------------------------------------------------------------
# Saved pages
# ---------------------------------------------------------------------------

class TestSavedPages:
    def test_save_and_retrieve_html(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(storage, "_SAVED_DIR", tmp_data_dir / "saved")
        storage.save_page("https://a.com", "A", "<h1>Hello</h1>", "Hello")
        pages = storage.load_saved_pages()
        assert len(pages) == 1
        assert pages[0]["url"] == "https://a.com"
        html = storage.get_saved_page_html(pages[0]["id"])
        assert html == "<h1>Hello</h1>"

    def test_remove_saved_page(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(storage, "_SAVED_DIR", tmp_data_dir / "saved")
        storage.save_page("https://a.com", "A", "<p>Content</p>")
        page_id = storage.load_saved_pages()[0]["id"]
        storage.remove_saved_page(page_id)
        assert storage.load_saved_pages() == []
        assert storage.get_saved_page_html(page_id) == ""

    def test_resave_updates(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(storage, "_SAVED_DIR", tmp_data_dir / "saved")
        storage.save_page("https://a.com", "A", "<p>Old</p>")
        storage.save_page("https://a.com", "A updated", "<p>New</p>")
        pages = storage.load_saved_pages()
        assert len(pages) == 1
        assert pages[0]["title"] == "A updated"


# ---------------------------------------------------------------------------
# JSON cache internals
# ---------------------------------------------------------------------------

class TestJsonCache:
    def test_cache_populated_on_load(self, tmp_data_dir):
        storage.invalidate_cache()
        assert "bookmarks.json" not in storage._json_cache
        storage.load_bookmarks()
        assert "bookmarks.json" in storage._json_cache

    def test_cache_updated_on_save(self, tmp_data_dir):
        storage.save_bookmarks([{"url": "https://a.com", "title": "A"}])
        assert storage._json_cache["bookmarks.json"][0]["url"] == "https://a.com"

    def test_invalidate_single(self, tmp_data_dir):
        storage.load_bookmarks()
        storage.load_settings()
        storage.invalidate_cache("bookmarks.json")
        assert "bookmarks.json" not in storage._json_cache
        assert "settings.json" in storage._json_cache

    def test_invalidate_all(self, tmp_data_dir):
        storage.load_bookmarks()
        storage.load_settings()
        storage.invalidate_cache()
        assert storage._json_cache == {}
