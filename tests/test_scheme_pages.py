"""Smoke tests: every shroud:// page must render without raising.

These tests don't validate the markup beyond a few high-signal anchors;
their value is that they exercise every page generator in scheme.py
under a clean data dir, catching crashes from refactors, missing
imports, or page methods that assume a fixture they don't have.
"""

import types

import pytest

from browser.scheme import ShroudSchemeHandler, _PAGES


class _FakeMainWindow:
    """Just enough of the MainWindow surface to satisfy page renderers
    that reach for ``self.parent()`` to look up settings, watchers, or
    the warc capture state."""

    def __init__(self):
        self._settings = {}
        self._page_watcher = types.SimpleNamespace(
            watches=[],
            history={},
            running=False,
        )
        # WARC capture surface
        self._warc_capture = types.SimpleNamespace(
            is_active=False,
            record_count=0,
            page_count=0,
            captured_urls=[],
        )
        self._bg_activity = types.SimpleNamespace(
            get_all_workers=lambda: {},
            get_all_subscriptions=lambda: {},
        )
        self._extension_manager = types.SimpleNamespace(
            get_extensions=lambda: [],
        )
        self._profile_manager = types.SimpleNamespace(
            list_profiles=lambda: [],
        )


class _FakeProfile:
    def httpUserAgent(self):
        return "Shroudbyte/test"


@pytest.fixture
def handler(tmp_data_dir, qapp):
    # parent() must be a QObject for Qt, so we pass None to the
    # constructor and then override parent() at the instance level
    # to return our stub. Pages only call .parent() to look up
    # attributes, not to walk a real Qt tree.
    h = ShroudSchemeHandler(profile=_FakeProfile(), parent=None)
    fake = _FakeMainWindow()
    h.parent = lambda: fake  # type: ignore[method-assign]
    return h


PAGE_TO_METHOD = {
    "newtab":      None,  # handled by generate_new_tab_html, not a method
    "settings":    "_page_settings",
    "bookmarks":   "_page_bookmarks",
    "history":     "_page_history",
    "privacy":     "_page_privacy",
    "watches":     "_page_watches",
    "screentime":  "_page_screentime",
    "saved":       "_page_saved",
    "apps":        "_page_apps",
    "permissions": "_page_permissions",
    "background":  "_page_background",
    "captures":    "_page_captures",
    "extensions":  "_page_extensions",
    "profiles":    "_page_profiles",
    "sessions":    "_page_sessions",
    "about":       "_page_about",
    "shortcuts":   "_page_shortcuts",
    "crashes":     "_page_crashes",
    "addresses":   "_page_addresses",
}


class TestEveryPageRenders:
    @pytest.mark.parametrize("page_name", list(_PAGES.keys()))
    def test_page_renders_clean(self, handler, page_name):
        if page_name == "newtab":
            from browser.scheme import generate_new_tab_html
            html = generate_new_tab_html()
        else:
            method_name = PAGE_TO_METHOD[page_name]
            html = getattr(handler, method_name)()
        # Each page is a full HTML document.
        assert html.lstrip().startswith("<!DOCTYPE"), \
            f"{page_name} does not start with <!DOCTYPE>"
        # Reasonable size — anything under a few hundred bytes is likely
        # an error stub or empty placeholder.
        assert len(html) > 500, f"{page_name} suspiciously short ({len(html)})"

    def test_error_page_renders(self, handler):
        # A request for an unknown shroud:// host falls through to
        # _page_error; make sure that path still works.
        html = handler._page_error("shroud://made-up")
        assert "shroud://made-up" in html


class TestPagesAreUnique:
    def test_no_duplicate_page_names(self):
        names = list(_PAGES.keys())
        assert len(names) == len(set(names))

    def test_every_listed_page_has_a_method(self, handler):
        for name in _PAGES:
            if name == "newtab":
                continue  # newtab handled differently
            method_name = PAGE_TO_METHOD.get(name)
            assert method_name is not None, \
                f"{name} listed in _PAGES but absent from PAGE_TO_METHOD"
            assert callable(getattr(handler, method_name, None)), \
                f"{name} maps to missing method {method_name}"


class TestCrossLinkedNavigation:
    def test_about_lists_internal_pages(self, handler):
        html = handler._page_about()
        # The about page enumerates every internal page; spot check.
        assert "shroud://settings" in html
        assert "shroud://crashes" in html
        assert "shroud://addresses" in html

    def test_error_page_offers_navigation(self, handler):
        html = handler._page_error("shroud://typo")
        # Helpful error page links back to known pages.
        assert "shroud://newtab" in html or "shroud://settings" in html
