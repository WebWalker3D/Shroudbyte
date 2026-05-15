"""Tests for browser.site_settings — per-host override wrapper around db."""

from browser import site_settings


class TestSiteSettings:
    def test_unknown_host_returns_defaults(self, tmp_data_dir):
        s = site_settings.get_site_settings("never-visited.com")
        # Every default key should be present.
        for key, default in site_settings.SITE_SETTING_KEYS.items():
            assert s[key] == default

    def test_override_one_setting_leaves_others_default(self, tmp_data_dir):
        site_settings.set_site_setting("example.com", "js_enabled", False)
        s = site_settings.get_site_settings("example.com")
        assert s["js_enabled"] is False
        assert s["cookies_enabled"] is True
        assert s["referrer_policy"] == "default"

    def test_unknown_key_is_rejected(self, tmp_data_dir):
        site_settings.set_site_setting("example.com", "moon_phase", "waxing")
        s = site_settings.get_site_settings("example.com")
        assert "moon_phase" not in s

    def test_customized_hosts_listed(self, tmp_data_dir):
        site_settings.set_site_setting("a.com", "js_enabled", False)
        site_settings.set_site_setting("b.com", "images_enabled", False)
        hosts = site_settings.get_all_customized_hosts()
        assert set(hosts) == {"a.com", "b.com"}

    def test_remove_clears_overrides(self, tmp_data_dir):
        site_settings.set_site_setting("c.com", "js_enabled", False)
        site_settings.remove_site_settings("c.com")
        # Back to defaults.
        assert site_settings.get_site_settings("c.com")["js_enabled"] is True
        assert "c.com" not in site_settings.get_all_customized_hosts()
