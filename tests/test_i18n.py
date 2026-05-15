"""Tests for browser.i18n — translation scaffolding."""

from browser import i18n


class TestIdentityFallback:
    def test_returns_input_when_no_catalog(self):
        # With no compiled .mo files shipped, _() is the identity.
        assert i18n._("Hello") == "Hello"
        assert i18n.gettext_("Hello") == "Hello"

    def test_unicode(self):
        assert i18n._("Héllo, world") == "Héllo, world"

    def test_set_language_to_none_resets(self):
        i18n.set_language("xx_NONEXISTENT")
        # Should not raise, and identity behavior is preserved.
        assert i18n._("anything") == "anything"
        i18n.set_language(None)
        assert i18n._("anything") == "anything"


class TestAvailableLanguages:
    def test_empty_when_no_locale_dir(self, monkeypatch, tmp_path):
        # Point i18n at an empty temp directory.
        monkeypatch.setattr(i18n, "_LOCALE_DIR", tmp_path / "nope")
        assert i18n.available_languages() == []

    def test_finds_mo_files(self, monkeypatch, tmp_path):
        locale = tmp_path / "locale"
        for lang in ("fr", "de"):
            mo = locale / lang / "LC_MESSAGES" / "shroudbyte.mo"
            mo.parent.mkdir(parents=True)
            mo.write_bytes(b"")
        monkeypatch.setattr(i18n, "_LOCALE_DIR", locale)
        assert i18n.available_languages() == ["de", "fr"]
