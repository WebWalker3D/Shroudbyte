"""Tests for browser.adblock — ad/tracker blocking interceptor helpers."""

import pytest
from unittest.mock import patch, MagicMock

from browser.adblock import (
    AdBlockInterceptor,
    PageTracker,
    TRACKING_PARAMS,
    DEFAULT_BLOCKED,
    _PAGE_DATA_MAX,
)


# ---------------------------------------------------------------------------
# Helpers: build a minimal interceptor without Qt or real storage
# ---------------------------------------------------------------------------

def _make_interceptor(blocked_hosts=None):
    """Create an AdBlockInterceptor with Qt super().__init__ and reload_hosts
    bypassed, using the given blocked_hosts set directly."""
    with patch.object(AdBlockInterceptor, "__init__", lambda self, *a, **kw: None):
        obj = AdBlockInterceptor.__new__(AdBlockInterceptor)
        obj._enabled = True
        obj._blocked_hosts = blocked_hosts or set()
        obj._blocked_count = 0
        obj.do_not_track = True
        obj.strip_tracking = True
        obj._http_auth = {}
        obj._page_data = {}
        obj._site_exceptions = {}
    return obj


# ---------------------------------------------------------------------------
# _match_blocked
# ---------------------------------------------------------------------------

class TestMatchBlocked:
    def test_exact_domain_match(self):
        ab = _make_interceptor({"ads.example.com"})
        assert ab._match_blocked("ads.example.com") == "ads.example.com"

    def test_subdomain_match(self):
        """A subdomain of a blocked domain should match the parent rule."""
        ab = _make_interceptor({"example.com"})
        assert ab._match_blocked("sub.example.com") == "example.com"
        assert ab._match_blocked("deep.sub.example.com") == "example.com"

    def test_no_match(self):
        ab = _make_interceptor({"ads.example.com"})
        assert ab._match_blocked("safe.example.org") is None

    def test_partial_name_does_not_match(self):
        """'notexample.com' should NOT match a rule for 'example.com'."""
        ab = _make_interceptor({"example.com"})
        assert ab._match_blocked("notexample.com") is None

    def test_empty_blocked_set(self):
        ab = _make_interceptor(set())
        assert ab._match_blocked("anything.com") is None


# ---------------------------------------------------------------------------
# Third-party detection (_is_third_party)
# ---------------------------------------------------------------------------

class TestThirdParty:
    def test_same_domain_is_not_third_party(self):
        assert AdBlockInterceptor._is_third_party("example.com", "example.com") is False

    def test_www_prefix_stripped(self):
        assert AdBlockInterceptor._is_third_party("www.example.com", "example.com") is False
        assert AdBlockInterceptor._is_third_party("example.com", "www.example.com") is False

    def test_subdomain_of_first_party_not_third_party(self):
        assert AdBlockInterceptor._is_third_party("example.com", "cdn.example.com") is False

    def test_first_party_is_subdomain_of_request(self):
        """If the first party is a subdomain of the request host, not third-party."""
        assert AdBlockInterceptor._is_third_party("sub.example.com", "example.com") is False

    def test_different_domain_is_third_party(self):
        assert AdBlockInterceptor._is_third_party("example.com", "ads.tracker.net") is True

    def test_empty_hosts(self):
        assert AdBlockInterceptor._is_third_party("", "example.com") is False
        assert AdBlockInterceptor._is_third_party("example.com", "") is False
        assert AdBlockInterceptor._is_third_party("", "") is False


# ---------------------------------------------------------------------------
# Tracking parameter stripping (TRACKING_PARAMS set)
# ---------------------------------------------------------------------------

class TestTrackingParams:
    def test_utm_params_present(self):
        for p in ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"):
            assert p in TRACKING_PARAMS

    def test_click_id_params_present(self):
        for p in ("fbclid", "gclid", "msclkid", "dclid"):
            assert p in TRACKING_PARAMS

    def test_ga_params_present(self):
        assert "_ga" in TRACKING_PARAMS
        assert "_gl" in TRACKING_PARAMS

    def test_non_tracking_param_absent(self):
        assert "q" not in TRACKING_PARAMS
        assert "page" not in TRACKING_PARAMS


# ---------------------------------------------------------------------------
# _PAGE_DATA_MAX eviction
# ---------------------------------------------------------------------------

class TestPageDataEviction:
    def test_eviction_when_over_limit(self):
        ab = _make_interceptor()
        # Insert _PAGE_DATA_MAX + 10 entries
        total = _PAGE_DATA_MAX + 10
        for i in range(total):
            ab._ensure_page_data(f"host-{i}.example.com")

        # The dict should never exceed _PAGE_DATA_MAX entries
        assert len(ab._page_data) <= _PAGE_DATA_MAX

    def test_oldest_entries_evicted_first(self):
        ab = _make_interceptor()
        # Fill to exactly _PAGE_DATA_MAX
        for i in range(_PAGE_DATA_MAX):
            ab._ensure_page_data(f"host-{i}.example.com")
        assert len(ab._page_data) == _PAGE_DATA_MAX

        # The first entry should still be present
        assert "host-0.example.com" in ab._page_data

        # Add one more — the oldest (host-0) should be evicted
        ab._ensure_page_data("overflow.example.com")
        assert "host-0.example.com" not in ab._page_data
        assert "overflow.example.com" in ab._page_data
        assert len(ab._page_data) == _PAGE_DATA_MAX

    def test_existing_key_does_not_trigger_eviction(self):
        ab = _make_interceptor()
        for i in range(_PAGE_DATA_MAX):
            ab._ensure_page_data(f"host-{i}.example.com")

        # Re-access an existing key — should NOT evict anything
        tracker = ab._ensure_page_data("host-0.example.com")
        assert len(ab._page_data) == _PAGE_DATA_MAX
        assert isinstance(tracker, PageTracker)


# ---------------------------------------------------------------------------
# PageTracker basics
# ---------------------------------------------------------------------------

class TestPageTracker:
    def test_initial_state(self):
        pt = PageTracker()
        assert pt.blocked == {}
        assert pt.third_party == {}
        assert pt.stripped_params == set()

    def test_ensure_page_data_returns_tracker(self):
        ab = _make_interceptor()
        tracker = ab._ensure_page_data("example.com")
        assert isinstance(tracker, PageTracker)

    def test_get_page_data(self):
        ab = _make_interceptor()
        ab._ensure_page_data("example.com")
        result = ab.get_page_data("example.com")
        assert result is not None
        assert isinstance(result, PageTracker)

    def test_get_page_data_lowercases_lookup(self):
        ab = _make_interceptor()
        ab._ensure_page_data("example.com")
        # get_page_data lowercases its argument before lookup
        result = ab.get_page_data("Example.COM")
        assert result is not None

    def test_clear_page_data_single(self):
        ab = _make_interceptor()
        ab._ensure_page_data("a.com")
        ab._ensure_page_data("b.com")
        ab.clear_page_data("a.com")
        assert ab.get_page_data("a.com") is None
        assert ab.get_page_data("b.com") is not None

    def test_clear_page_data_all(self):
        ab = _make_interceptor()
        ab._ensure_page_data("a.com")
        ab._ensure_page_data("b.com")
        ab.clear_page_data()
        assert ab.get_page_data("a.com") is None
        assert ab.get_page_data("b.com") is None
