"""Background Activity Manager — monitor service workers and push subscriptions."""

import time
from PyQt6.QtCore import QObject


_SW_REGISTER_PREFIX = "__SHROUD_SW_REGISTER__:"
_PUSH_SUB_PREFIX = "__SHROUD_PUSH_SUB__:"


class BackgroundActivityManager(QObject):
    """Tracks service worker registrations and push subscriptions per site."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registrations: dict[str, dict] = {}  # host -> {scope, registered_at, ...}
        self._push_subscriptions: dict[str, dict] = {}  # host -> {endpoint, subscribed_at, ...}

    def register_service_worker(self, host: str, scope: str):
        self._registrations[host] = {
            "scope": scope,
            "registered_at": time.time(),
            "last_active": time.time(),
            "paused": False,
        }

    def unregister_service_worker(self, host: str):
        self._registrations.pop(host, None)

    def register_push_subscription(self, host: str, endpoint: str):
        self._push_subscriptions[host] = {
            "endpoint": endpoint,
            "subscribed_at": time.time(),
        }

    def revoke_push_subscription(self, host: str):
        self._push_subscriptions.pop(host, None)

    def pause_worker(self, host: str):
        if host in self._registrations:
            self._registrations[host]["paused"] = True

    def resume_worker(self, host: str):
        if host in self._registrations:
            self._registrations[host]["paused"] = False

    def get_all_workers(self) -> dict:
        return dict(self._registrations)

    def get_all_subscriptions(self) -> dict:
        return dict(self._push_subscriptions)


def get_background_activity_js() -> str:
    """Return JS that hooks service worker registration and push subscription."""
    return """(function() {
    if (window.__shroudBgActivity) return;
    window.__shroudBgActivity = true;

    // Hook navigator.serviceWorker.register()
    if (navigator.serviceWorker && navigator.serviceWorker.register) {
        var origRegister = navigator.serviceWorker.register.bind(navigator.serviceWorker);
        navigator.serviceWorker.register = function(scriptURL, options) {
            var scope = (options && options.scope) || scriptURL;
            try {
                console.log('__SHROUD_SW_REGISTER__:' + JSON.stringify({
                    host: location.hostname,
                    scope: scope.toString()
                }));
            } catch(e) {}
            return origRegister(scriptURL, options);
        };
    }

    // Hook PushManager.prototype.subscribe
    if (typeof PushManager !== 'undefined' && PushManager.prototype.subscribe) {
        var origSubscribe = PushManager.prototype.subscribe;
        PushManager.prototype.subscribe = function(options) {
            var self = this;
            return origSubscribe.call(this, options).then(function(sub) {
                try {
                    console.log('__SHROUD_PUSH_SUB__:' + JSON.stringify({
                        host: location.hostname,
                        endpoint: sub.endpoint || ''
                    }));
                } catch(e) {}
                return sub;
            });
        };
    }
})();"""
