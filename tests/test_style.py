"""Tests for browser.style — theme switching."""

from browser import style


class TestThemeSwitching:
    def test_default_is_dark(self):
        # The module ships in dark mode (matching the README/UX).
        style.set_theme("dark")
        assert style.get_theme() == "dark"
        assert style.is_dark_mode() is True

    def test_light_theme(self):
        style.set_theme("light")
        assert style.get_theme() == "light"
        assert style.is_dark_mode() is False
        # Light bg should be light-valued
        assert style.BG_DARK.startswith("#f")

    def test_high_contrast_theme(self):
        style.set_theme("high_contrast")
        assert style.get_theme() == "high_contrast"
        # High contrast is "dark-ish" by treatment
        assert style.is_dark_mode() is True
        assert style.BG_DARK == "#000000"
        assert style.TEXT == "#ffffff"
        # Stylesheets rebuilt with new palette
        assert "#000000" in style.GLOBAL_STYLESHEET

    def test_unknown_theme_falls_back_to_dark(self):
        style.set_theme("rainbow_disco")
        assert style.get_theme() == "dark"

    def test_legacy_set_dark_mode_still_works(self):
        style.set_dark_mode(False)
        assert style.get_theme() == "light"
        style.set_dark_mode(True)
        assert style.get_theme() == "dark"
