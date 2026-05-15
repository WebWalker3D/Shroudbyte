"""Tests for browser.background_activity — SW registration + push tracking."""

import time

import pytest

from browser.background_activity import (
    BackgroundActivityManager,
    get_background_activity_js,
)


@pytest.fixture
def mgr(qapp):
    """QObject needs a QApplication on the running thread; pytest-qt gives us qapp."""
    return BackgroundActivityManager(parent=None)


class TestServiceWorker:
    def test_register_records_metadata(self, mgr):
        mgr.register_service_worker("a.com", "/")
        workers = mgr.get_all_workers()
        assert "a.com" in workers
        assert workers["a.com"]["scope"] == "/"
        assert workers["a.com"]["paused"] is False
        assert workers["a.com"]["registered_at"] > 0

    def test_unregister_removes(self, mgr):
        mgr.register_service_worker("a.com", "/")
        mgr.unregister_service_worker("a.com")
        assert "a.com" not in mgr.get_all_workers()

    def test_unregister_missing_is_safe(self, mgr):
        mgr.unregister_service_worker("never-registered")  # must not raise

    def test_pause_resume(self, mgr):
        mgr.register_service_worker("a.com", "/")
        mgr.pause_worker("a.com")
        assert mgr.get_all_workers()["a.com"]["paused"] is True
        mgr.resume_worker("a.com")
        assert mgr.get_all_workers()["a.com"]["paused"] is False

    def test_pause_unknown_is_safe(self, mgr):
        mgr.pause_worker("ghost")  # must not raise
        assert mgr.get_all_workers() == {}

    def test_re_register_replaces_metadata(self, mgr):
        mgr.register_service_worker("a.com", "/v1")
        mgr.register_service_worker("a.com", "/v2")
        assert mgr.get_all_workers()["a.com"]["scope"] == "/v2"


class TestPushSubscriptions:
    def test_subscribe_records_endpoint(self, mgr):
        mgr.register_push_subscription("a.com", "https://push.example/sub/abc")
        subs = mgr.get_all_subscriptions()
        assert subs["a.com"]["endpoint"] == "https://push.example/sub/abc"
        assert subs["a.com"]["subscribed_at"] > 0

    def test_revoke(self, mgr):
        mgr.register_push_subscription("a.com", "x")
        mgr.revoke_push_subscription("a.com")
        assert mgr.get_all_subscriptions() == {}


class TestInjectedJs:
    def test_idempotency_guard(self):
        js = get_background_activity_js()
        assert "__shroudBgActivity" in js

    def test_hooks_documented_apis(self):
        js = get_background_activity_js()
        assert "navigator.serviceWorker.register" in js
        assert "PushManager.prototype.subscribe" in js

    def test_uses_known_prefixes(self):
        # The IPC dispatcher in webview.py keys on these strings, so the
        # JS must emit them verbatim.
        js = get_background_activity_js()
        assert "__SHROUD_SW_REGISTER__" in js
        assert "__SHROUD_PUSH_SUB__" in js
