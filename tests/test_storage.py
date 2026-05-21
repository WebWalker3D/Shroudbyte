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


class TestPermissionExpiry:
    """The permission_ttl_days setting drives an expires_at field that
    get_permission must honor — expired entries should return None and
    be cleaned up from disk."""

    def test_expired_permission_returns_none(self, tmp_data_dir, monkeypatch):
        import time as _time
        now = [1700000000.0]
        monkeypatch.setattr(_time, "time", lambda: now[0])
        # Also patch the time reference inside storage.
        monkeypatch.setattr(storage.time, "time", lambda: now[0])

        storage.set_permission("example.com", "camera", "allow", ttl_days=7)
        assert storage.get_permission("example.com", "camera") == "allow"

        # Fast-forward 8 days.
        now[0] += 8 * 86400
        assert storage.get_permission("example.com", "camera") is None

    def test_expired_permission_is_removed_from_disk(self, tmp_data_dir, monkeypatch):
        import time as _time
        now = [1700000000.0]
        monkeypatch.setattr(storage.time, "time", lambda: now[0])
        storage.set_permission("example.com", "camera", "allow", ttl_days=1)
        now[0] += 2 * 86400
        # Triggering the read also cleans up.
        storage.get_permission("example.com", "camera")
        perms = storage.load_permissions()
        assert "example.com" not in perms or "camera" not in perms.get("example.com", {})

    def test_ttl_zero_means_never_expires(self, tmp_data_dir, monkeypatch):
        import time as _time
        now = [1700000000.0]
        monkeypatch.setattr(storage.time, "time", lambda: now[0])
        storage.set_permission("example.com", "camera", "allow", ttl_days=0)
        # A century later — still here.
        now[0] += 100 * 365 * 86400
        assert storage.get_permission("example.com", "camera") == "allow"

    def test_legacy_string_format_has_no_expiry(self, tmp_data_dir):
        # Pre-TTL format stored permissions as bare strings, not dicts.
        # The read path should still return them.
        storage.save_permissions({
            "example.com": {"camera": "allow", "mic": "deny"},
        })
        assert storage.get_permission("example.com", "camera") == "allow"
        assert storage.get_permission("example.com", "mic") == "deny"


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


class TestNetscapeBookmarkParse:
    """Folder nesting must survive the Netscape HTML round-trip."""

    def test_flat(self, tmp_data_dir):
        html = '''
<DL><p>
  <DT><A HREF="https://a.com">A</A>
  <DT><A HREF="https://b.com">B</A>
</DL>
'''
        entries = storage.parse_netscape_bookmarks(html)
        assert [(e["url"], e["folder"]) for e in entries] == [
            ("https://a.com", ""),
            ("https://b.com", ""),
        ]

    def test_nested_folders(self, tmp_data_dir):
        html = '''
<DL><p>
  <DT><H3>Work</H3>
  <DL><p>
    <DT><A HREF="https://w1.com">W1</A>
    <DT><H3>Research</H3>
    <DL><p>
      <DT><A HREF="https://r1.com">R1</A>
    </DL><p>
    <DT><A HREF="https://w2.com">W2</A>
  </DL><p>
  <DT><A HREF="https://top.com">Top</A>
</DL>
'''
        entries = storage.parse_netscape_bookmarks(html)
        got = [(e["url"], e["folder"]) for e in entries]
        assert got == [
            ("https://w1.com", "Work"),
            ("https://r1.com", "Work/Research"),
            ("https://w2.com", "Work"),
            ("https://top.com", ""),
        ]

    def test_html_entities_in_titles_and_folders(self, tmp_data_dir):
        html = '''
<DL><p>
  <DT><H3>Tom &amp; Jerry</H3>
  <DL><p>
    <DT><A HREF="https://example.com/?x=1&amp;y=2">A &amp; B</A>
  </DL>
</DL>
'''
        entries = storage.parse_netscape_bookmarks(html)
        assert len(entries) == 1
        assert entries[0]["title"] == "A & B"
        assert entries[0]["folder"] == "Tom & Jerry"
        assert entries[0]["url"] == "https://example.com/?x=1&y=2"


class TestNetscapeBookmarkRender:
    def test_round_trip_preserves_folders(self, tmp_data_dir):
        original = [
            {"title": "Top", "url": "https://top.com",
             "folder": "", "added": 1700000000},
            {"title": "W1", "url": "https://w1.com",
             "folder": "Work", "added": 1700000001},
            {"title": "R1", "url": "https://r1.com",
             "folder": "Work/Research", "added": 1700000002},
            {"title": "Personal-A", "url": "https://a.com",
             "folder": "Personal", "added": 1700000003},
        ]
        html = storage.render_netscape_bookmarks(original)
        parsed = storage.parse_netscape_bookmarks(html)
        # Sort by URL for stable comparison; ordering across folders is
        # not part of the contract, but each URL should keep its folder.
        round_tripped = {p["url"]: p["folder"] for p in parsed}
        expected = {b["url"]: b["folder"] for b in original}
        assert round_tripped == expected

    def test_flat_list_emits_no_h3(self, tmp_data_dir):
        bookmarks = [
            {"title": "A", "url": "https://a.com", "folder": "", "added": 0},
            {"title": "B", "url": "https://b.com", "folder": "", "added": 0},
        ]
        html = storage.render_netscape_bookmarks(bookmarks)
        assert "<H3>" not in html
        assert "https://a.com" in html and "https://b.com" in html

    def test_html_entities_escaped(self, tmp_data_dir):
        bookmarks = [{
            "title": "A & B",
            "url": "https://x.com/?q=1&y=2",
            "folder": "Tom & Jerry",
            "added": 0,
        }]
        html = storage.render_netscape_bookmarks(bookmarks)
        assert "&amp;" in html
        # And the round trip should decode it back correctly.
        [parsed] = storage.parse_netscape_bookmarks(html)
        assert parsed["title"] == "A & B"
        assert parsed["url"] == "https://x.com/?q=1&y=2"
        assert parsed["folder"] == "Tom & Jerry"
