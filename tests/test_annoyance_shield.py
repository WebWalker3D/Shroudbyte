"""Tests for browser.annoyance_shield — JS payload sanity check."""

from browser.annoyance_shield import get_annoyance_shield_js


class TestAnnoyanceShieldJs:
    def test_idempotency_guard(self):
        js = get_annoyance_shield_js()
        # Re-injection must short-circuit.
        assert "__shroudAnnoyanceShield" in js

    def test_is_iife(self):
        js = get_annoyance_shield_js().strip()
        assert js.startswith("(function()") or js.startswith("(function ()")
        assert js.endswith("})();")

    def test_targets_documented_annoyances(self):
        # README claims: cookie consent, chat widgets, newsletter modals,
        # anti-adblock walls, floating video players, app install banners.
        js = get_annoyance_shield_js().lower()
        for needle in (
            "intercom",       # chat widget
            "consent",        # cookie banners
            "z-index",        # overlay heuristic
        ):
            assert needle in js, f"annoyance shield missing: {needle}"

    def test_runs_periodically(self):
        # The shield re-scans the page on a timer, not just on load.
        js = get_annoyance_shield_js()
        assert "setInterval" in js or "setTimeout" in js
