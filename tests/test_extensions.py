"""Tests for browser.extensions — content script extension manager."""

import json

import pytest

from browser import extensions, storage
from browser.extensions import ExtensionManager


def _write_extension(root, name, manifest, files=None):
    """Create an extension directory with a manifest plus referenced files."""
    ext_dir = root / "extensions" / name
    ext_dir.mkdir(parents=True)
    (ext_dir / "manifest.json").write_text(json.dumps(manifest))
    for fname, content in (files or {}).items():
        (ext_dir / fname).write_text(content)
    return ext_dir


@pytest.fixture
def manager(tmp_data_dir):
    return ExtensionManager()


class TestLoading:
    def test_empty_directory(self, manager):
        assert manager.get_extensions() == []

    def test_loads_manifest(self, tmp_data_dir):
        _write_extension(tmp_data_dir, "demo", {
            "name": "Demo",
            "version": "0.1",
            "description": "Test",
            "content_scripts": [{
                "matches": ["*://*.example.com/*"],
                "js": ["main.js"],
            }],
        }, files={"main.js": "console.log('x');"})

        m = ExtensionManager()
        exts = m.get_extensions()
        assert len(exts) == 1
        assert exts[0].name == "Demo"
        assert exts[0].version == "0.1"
        assert exts[0].enabled is True
        assert len(exts[0].content_scripts) == 1

    def test_corrupt_manifest_is_skipped(self, tmp_data_dir):
        ext_dir = tmp_data_dir / "extensions" / "broken"
        ext_dir.mkdir(parents=True)
        (ext_dir / "manifest.json").write_text("not json {{{")
        m = ExtensionManager()
        assert m.get_extensions() == []


class TestEnableDisable:
    def test_disable_persists(self, tmp_data_dir):
        _write_extension(tmp_data_dir, "demo", {"name": "Demo"})
        m = ExtensionManager()
        m.disable("demo")
        # Reload from disk — state should persist.
        m2 = ExtensionManager()
        [ext] = m2.get_extensions()
        assert ext.enabled is False

    def test_disabled_extension_doesnt_inject(self, tmp_data_dir):
        _write_extension(tmp_data_dir, "demo", {
            "name": "Demo",
            "content_scripts": [{
                "matches": ["<all_urls>"],
                "js": ["a.js"],
            }],
        }, files={"a.js": "alert(1);"})
        m = ExtensionManager()
        m.disable("demo")
        js, _css = m.get_scripts_for_url("https://anything.com/")
        assert js == ""


class TestUrlMatching:
    @pytest.mark.parametrize("pattern,url,expected", [
        ("<all_urls>", "https://example.com/", True),
        ("*://*.example.com/*", "https://www.example.com/foo", True),
        ("*://*.example.com/*", "https://example.com/foo", True),
        ("*://*.example.com/*", "https://other.com/foo", False),
        ("https://github.com/*", "https://github.com/x", True),
        ("https://github.com/*", "http://github.com/x", False),
    ])
    def test_match(self, pattern, url, expected):
        assert ExtensionManager._url_matches(url, [pattern]) is expected

    def test_returns_first_match_in_list(self):
        # Order shouldn't matter — any match wins.
        assert ExtensionManager._url_matches(
            "https://example.com/", ["https://other.com/*", "<all_urls>"]
        ) is True


class TestScriptInjection:
    def test_combines_matching_scripts(self, tmp_data_dir):
        _write_extension(tmp_data_dir, "a", {
            "name": "A",
            "content_scripts": [{
                "matches": ["<all_urls>"],
                "js": ["a.js"],
                "css": ["a.css"],
            }],
        }, files={"a.js": "/*A*/", "a.css": "a{}"})
        _write_extension(tmp_data_dir, "b", {
            "name": "B",
            "content_scripts": [{
                "matches": ["<all_urls>"],
                "js": ["b.js"],
            }],
        }, files={"b.js": "/*B*/"})

        m = ExtensionManager()
        js, css = m.get_scripts_for_url("https://x.com/")
        assert "/*A*/" in js and "/*B*/" in js
        assert "a{}" in css

    def test_run_at_filter(self, tmp_data_dir):
        _write_extension(tmp_data_dir, "early", {
            "name": "Early",
            "content_scripts": [{
                "matches": ["<all_urls>"],
                "js": ["e.js"],
                "run_at": "document_start",
            }],
        }, files={"e.js": "/*early*/"})
        _write_extension(tmp_data_dir, "late", {
            "name": "Late",
            "content_scripts": [{
                "matches": ["<all_urls>"],
                "js": ["l.js"],
                "run_at": "document_idle",
            }],
        }, files={"l.js": "/*late*/"})

        m = ExtensionManager()
        early_js, _ = m.get_scripts_for_url("https://x", run_at="document_start")
        late_js, _ = m.get_scripts_for_url("https://x", run_at="document_idle")
        assert "early" in early_js and "late" not in early_js
        assert "late" in late_js and "early" not in late_js

    def test_missing_referenced_file_is_silently_skipped(self, tmp_data_dir):
        _write_extension(tmp_data_dir, "missing", {
            "name": "M",
            "content_scripts": [{
                "matches": ["<all_urls>"],
                "js": ["does_not_exist.js"],
            }],
        })
        m = ExtensionManager()
        js, _ = m.get_scripts_for_url("https://x/")
        assert js == ""
