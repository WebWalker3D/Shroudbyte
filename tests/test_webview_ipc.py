"""Tests for the table-driven IPC dispatcher in browser.webview.

We construct a stub Page (just enough surface for the handlers) and
call _dispatch_ipc directly, so the test doesn't need a real WebEngine.
"""

import logging
import types

import pytest


class FakeView:
    pass


class FakeMW:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def _handle_link_hover(self, href, view):
        self.calls.append(("link_hover", (href, view)))

    def _handle_privacy_action(self, data):
        self.calls.append(("privacy", (data,)))

    def _handle_watch_action(self, data):
        self.calls.append(("watch", (data,)))

    def _handle_settings_action(self, data, view):
        self.calls.append(("settings", (data, view)))

    def _handle_page_action(self, data):
        self.calls.append(("page_action", (data,)))

    def _handle_perm_ledger_action(self, data):
        self.calls.append(("perm_ledger", (data,)))

    def _handle_form_draft(self, data):
        self.calls.append(("form_draft", (data,)))

    def _handle_pwa(self, data):
        self.calls.append(("pwa", (data,)))

    class _BG:
        def __init__(self, outer):
            self.outer = outer

        def register_service_worker(self, host, scope):
            self.outer.calls.append(("sw", (host, scope)))

        def register_push_subscription(self, host, endpoint):
            self.outer.calls.append(("push", (host, endpoint)))

    class _Clip:
        def __init__(self, outer):
            self.outer = outer

        def record(self, text, url):
            self.outer.calls.append(("clip", (text, url)))


@pytest.fixture
def page_and_mw():
    """Build a stand-in 'page' whose attribute surface matches what handlers touch."""
    from browser import webview_ipc

    mw = FakeMW()
    mw._bg_activity = FakeMW._BG(mw)
    mw._clipboard_history = FakeMW._Clip(mw)

    page = types.SimpleNamespace(
        _view_ref=FakeView(),
        url=lambda: types.SimpleNamespace(toString=lambda: "https://x"),
        _get_main_window=lambda: mw,
    )
    page._dispatch_ipc = lambda msg: webview_ipc.dispatch(page, msg)
    return page, mw


class TestDispatchRouting:
    def test_link_hover_route(self, page_and_mw):
        page, mw = page_and_mw
        assert page._dispatch_ipc('__SHROUD_LINK_HOVER__:{"href":"https://t"}') is True
        assert mw.calls == [("link_hover", ("https://t", page._view_ref))]

    def test_clipboard_is_raw_text_not_json(self, page_and_mw):
        page, mw = page_and_mw
        # No JSON parsing for clipboard — passes through verbatim.
        assert page._dispatch_ipc("__SHROUD_CLIP__:hello world") is True
        assert mw.calls == [("clip", ("hello world", "https://x"))]

    def test_service_worker_register(self, page_and_mw):
        page, mw = page_and_mw
        assert page._dispatch_ipc(
            '__SHROUD_SW_REGISTER__:{"host":"a.com","scope":"/"}'
        ) is True
        assert mw.calls == [("sw", ("a.com", "/"))]

    def test_unmatched_returns_false(self, page_and_mw):
        page, _mw = page_and_mw
        assert page._dispatch_ipc("just a regular log line") is False

    def test_malformed_json_logged_not_raised(self, page_and_mw, caplog):
        page, mw = page_and_mw
        with caplog.at_level(logging.ERROR, logger="shroudbyte.webview"):
            # Truncated JSON — the handler must not raise; failure is logged.
            ok = page._dispatch_ipc('__SHROUD_PRIVACY__:{"bad":')
        assert ok is True  # prefix matched, even though parse failed
        assert mw.calls == []
        assert any("privacy" in r.message for r in caplog.records)
