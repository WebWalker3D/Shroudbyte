"""Tests for browser.fingerprint — JS payload sanity check."""

from browser.fingerprint import get_fingerprint_resistance_js


class TestFingerprintJs:
    def test_idempotency_guard_present(self):
        # Re-injection should be a no-op; the script gates itself on a window flag.
        js = get_fingerprint_resistance_js()
        assert "__shroudFingerprintResistance" in js

    def test_covers_each_documented_surface(self):
        # README lists Canvas / WebGL / AudioContext / hardware concurrency /
        # device memory / screen resolution. Spot-check each name appears.
        js = get_fingerprint_resistance_js()
        for needle in (
            "HTMLCanvasElement",
            "WebGL",
            "AudioContext",
            "hardwareConcurrency",
            "deviceMemory",
            "screen",
        ):
            assert needle in js, f"missing fingerprint surface: {needle}"

    def test_is_wrapped_in_iife(self):
        js = get_fingerprint_resistance_js().strip()
        # Must start with an IIFE so it can't leak locals into page scope.
        assert js.startswith("(function()") or js.startswith("(function ()")
        assert js.endswith("})();")
