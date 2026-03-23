"""Tests for browser.pwa — PWA manifest detection and install logic."""

import json
from unittest.mock import patch, MagicMock

from browser.pwa import detect_manifest_js, install_pwa, _desktop_id


class TestDetectManifestJs:
    """detect_manifest_js() returns injectable JavaScript."""

    def test_returns_string(self):
        js = detect_manifest_js()
        assert isinstance(js, str)

    def test_contains_manifest_query(self):
        js = detect_manifest_js()
        assert 'link[rel="manifest"]' in js

    def test_contains_shroud_pwa_marker(self):
        js = detect_manifest_js()
        assert "__SHROUD_PWA__" in js

    def test_is_iife(self):
        """Should be a self-invoking function to avoid polluting global scope."""
        js = detect_manifest_js()
        assert js.strip().startswith("(function()")
        assert js.strip().endswith("})();") or js.strip().endswith("})();\n")

    def test_guard_against_double_injection(self):
        js = detect_manifest_js()
        assert "__shroudPWADetected" in js


class TestInstallPwa:
    """install_pwa() saves metadata and creates a desktop file."""

    def test_install_saves_app_data(self, tmp_data_dir):
        manifest = {
            "name": "My App",
            "short_name": "App",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#000000",
            "icons": [],
        }
        page_url = "https://example.com"
        manifest_url = "https://example.com/manifest.json"

        with patch("browser.pwa._create_desktop_file"):
            app = install_pwa(manifest, page_url, manifest_url)

        assert app["name"] == "My App"
        assert app["short_name"] == "App"
        assert app["display"] == "standalone"
        assert app["manifest_url"] == manifest_url
        assert "installed" in app

    def test_install_resolves_relative_start_url(self, tmp_data_dir):
        manifest = {
            "name": "Relative App",
            "start_url": "/app/start",
            "icons": [],
        }
        manifest_url = "https://example.com/assets/manifest.json"

        with patch("browser.pwa._create_desktop_file"):
            app = install_pwa(manifest, "https://example.com", manifest_url)

        assert app["start_url"] == "https://example.com/app/start"

    def test_install_picks_largest_icon(self, tmp_data_dir):
        manifest = {
            "name": "Icon App",
            "start_url": "https://example.com",
            "icons": [
                {"src": "/icon-64.png", "sizes": "64x64"},
                {"src": "/icon-192.png", "sizes": "192x192"},
                {"src": "/icon-48.png", "sizes": "48x48"},
            ],
        }
        manifest_url = "https://example.com/manifest.json"

        with patch("browser.pwa._create_desktop_file"), \
             patch("browser.pwa._download_icon", return_value="/tmp/icon.png") as dl:
            app = install_pwa(manifest, "https://example.com", manifest_url)

        # Should have tried to download the 192x192 icon
        dl.assert_called_once()
        icon_url_arg = dl.call_args[0][0]
        assert "icon-192.png" in icon_url_arg

    def test_install_defaults_for_missing_fields(self, tmp_data_dir):
        manifest = {}  # minimal / empty
        with patch("browser.pwa._create_desktop_file"):
            app = install_pwa(manifest, "https://example.com", "https://example.com/m.json")

        assert app["name"] == "Web App"  # default
        assert app["display"] == "standalone"  # default


class TestDesktopId:
    """_desktop_id produces a stable, unique identifier."""

    def test_deterministic(self):
        id1 = _desktop_id("https://example.com")
        id2 = _desktop_id("https://example.com")
        assert id1 == id2

    def test_different_for_different_urls(self):
        id1 = _desktop_id("https://a.com")
        id2 = _desktop_id("https://b.com")
        assert id1 != id2

    def test_prefix(self):
        assert _desktop_id("https://x.com").startswith("shroudbyte-pwa-")
