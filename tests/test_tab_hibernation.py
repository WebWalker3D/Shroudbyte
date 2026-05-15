"""Tests for the tab hibernation logic.

We exercise :func:`TabMixin._hibernate_idle_tabs` directly against a
hand-rolled stub stand-in for QTabWidget/QWebEngineView, so the test
doesn't need a live QApplication or real WebEngine pages.
"""

import time
import types

from browser.mixins.tabs import TabMixin


class FakeView:
    """Stand-in for QWebEngineView — has just the surface hibernation touches."""

    def __init__(self, url: str, title: str = "", last_active: float | None = None,
                 pinned: bool = False, deferred: str | None = None):
        self._url = url
        self._title = title
        self._last_active = last_active
        self._pinned = pinned
        self._deferred_url = deferred
        self.set_html_called_with: tuple[str, object] | None = None

    def url(self):
        return types.SimpleNamespace(toString=lambda: self._url)

    def title(self):
        return self._title

    def setHtml(self, html, base_url):
        self.set_html_called_with = (html, base_url)


class FakeTabs:
    """Minimal QTabWidget look-alike."""

    def __init__(self, views, current_index=0):
        self._views = views
        self._current = current_index

    def count(self):
        return len(self._views)

    def widget(self, i):
        return self._views[i]

    def currentIndex(self):
        return self._current

    def tabText(self, i):
        return self._views[i].title()


def _make_host(views, settings, current_index=0):
    """Build a TabMixin-bound host object with the minimum required surface."""
    host = TabMixin()
    host._tabs = FakeTabs(views, current_index)
    host._settings = settings
    return host


class TestHibernateIdleTabs:
    def test_disabled_by_default(self):
        views = [FakeView("https://a.com", last_active=0)]
        host = _make_host(views, {"tab_hibernate_minutes": 0})
        host._hibernate_idle_tabs()
        assert views[0].set_html_called_with is None
        assert views[0]._deferred_url is None

    def test_current_tab_never_hibernated(self):
        views = [
            FakeView("https://current.com", last_active=0),  # idle but current
            FakeView("https://other.com",   last_active=time.time()),
        ]
        host = _make_host(views, {"tab_hibernate_minutes": 1}, current_index=0)
        host._hibernate_idle_tabs()
        assert views[0].set_html_called_with is None

    def test_pinned_tab_never_hibernated(self):
        views = [
            FakeView("https://current.com", last_active=time.time()),
            FakeView("https://pinned.com",  last_active=0, pinned=True),
        ]
        host = _make_host(views, {"tab_hibernate_minutes": 1}, current_index=0)
        host._hibernate_idle_tabs()
        assert views[1].set_html_called_with is None

    def test_idle_non_current_tab_is_hibernated(self):
        long_ago = time.time() - 120 * 60
        views = [
            FakeView("https://current.com", last_active=time.time()),
            FakeView("https://idle.com", title="Idle", last_active=long_ago),
        ]
        host = _make_host(views, {"tab_hibernate_minutes": 10}, current_index=0)
        host._hibernate_idle_tabs()
        assert views[1]._deferred_url == "https://idle.com"
        assert views[1].set_html_called_with is not None
        html, _base = views[1].set_html_called_with
        assert "hibernated" in html.lower()

    def test_already_deferred_tab_not_re_hibernated(self):
        long_ago = time.time() - 120 * 60
        views = [
            FakeView("https://current.com", last_active=time.time()),
            FakeView(
                "https://lazy.com",
                last_active=long_ago,
                deferred="https://lazy.com",
            ),
        ]
        host = _make_host(views, {"tab_hibernate_minutes": 10}, current_index=0)
        host._hibernate_idle_tabs()
        # No further setHtml — it's already a placeholder.
        assert views[1].set_html_called_with is None

    def test_shroud_internal_pages_skipped(self):
        long_ago = time.time() - 120 * 60
        views = [
            FakeView("https://current.com", last_active=time.time()),
            FakeView("shroud://settings", last_active=long_ago),
        ]
        host = _make_host(views, {"tab_hibernate_minutes": 10}, current_index=0)
        host._hibernate_idle_tabs()
        assert views[1].set_html_called_with is None
