"""Tests for browser.updater — version compare and cache behavior."""

import json
import time

from browser import updater


class TestParseVersion:
    def test_basic(self):
        assert updater._parse_version("1.2.3") == (1, 2, 3)

    def test_v_prefix(self):
        assert updater._parse_version("v1.2.3") == (1, 2, 3)

    def test_extra_text(self):
        assert updater._parse_version("v1.2.3-rc4") == (1, 2, 3, 4)

    def test_ordering(self):
        assert updater._parse_version("1.0.0") < updater._parse_version("1.0.1")
        assert updater._parse_version("v1.10.0") > updater._parse_version("v1.2.0")

    def test_unparsable_is_oldest(self):
        assert updater._parse_version("") == (0,)
        assert updater._parse_version("garbage") == (0,)
        assert updater._parse_version("garbage") < updater._parse_version("0.0.1")


class TestCache:
    def test_load_missing_returns_empty(self, tmp_data_dir):
        assert updater._load_cache() == {}

    def test_round_trip(self, tmp_data_dir):
        payload = {
            "checked_at": time.time(),
            "result": {"latest": "2.0.0", "current": "1.0.0",
                       "url": "https://x", "notes": ""},
        }
        updater._save_cache(payload)
        loaded = updater._load_cache()
        assert loaded == payload

    def test_load_handles_corrupt_json(self, tmp_data_dir):
        (tmp_data_dir / "update_check.json").write_text("this is not json")
        # Must not raise; treat as no cache.
        assert updater._load_cache() == {}


class TestCheckForUpdate:
    """Force-cache path: when a fresh cache entry exists, no network call."""

    def test_uses_cached_result_when_fresh(self, tmp_data_dir, monkeypatch):
        cached = {"latest": "9.9.9", "current": "1.0.0",
                  "url": "https://example", "notes": "n"}
        updater._save_cache({"checked_at": time.time(), "result": cached})

        def _no_network(*a, **kw):
            raise AssertionError("urlopen should not be called when cache is fresh")
        monkeypatch.setattr(updater.urllib.request, "urlopen", _no_network)

        assert updater.check_for_update() == cached

    def test_no_update_when_current_is_newest(self, tmp_data_dir, monkeypatch):
        # Stub urlopen to return a release older than current.
        from browser import __version__
        class _FakeResp:
            def __init__(self, payload):
                self._payload = payload
            def read(self):
                return json.dumps(self._payload).encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def _fake_urlopen(req, timeout=None, context=None):
            return _FakeResp({"tag_name": "v0.0.1", "html_url": "x", "body": ""})

        monkeypatch.setattr(updater.urllib.request, "urlopen", _fake_urlopen)
        # Force network call past the cache
        assert updater.check_for_update(force=True) is None
        # And the negative result is cached so we don't re-call.
        assert updater._load_cache()["result"] is None
