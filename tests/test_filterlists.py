"""Tests for browser.filterlists — filter list parsing and cosmetic CSS generation."""

import pytest

from browser import filterlists
from browser.filterlists import (
    _parse_file,
    get_cosmetic_css,
    get_cosmetic_rules,
    invalidate_parse_cache,
    COOKIE_BANNER_SELECTORS,
    AD_ELEMENT_SELECTORS,
    _cosmetic_css_cache,
    _parse_cache,
)


# ---------------------------------------------------------------------------
# Parsing: hosts-format lines
# ---------------------------------------------------------------------------

class TestHostsFormat:
    def test_zero_prefix(self):
        domains, cosmetic = _parse_file("0.0.0.0 ads.example.com\n")
        assert "ads.example.com" in domains
        assert cosmetic == []

    def test_localhost_prefix(self):
        domains, _ = _parse_file("127.0.0.1 tracker.example.com\n")
        assert "tracker.example.com" in domains

    def test_localhost_itself_excluded(self):
        domains, _ = _parse_file("127.0.0.1 localhost\n")
        assert "localhost" not in domains

    def test_no_dot_excluded(self):
        """Entries without a dot (e.g., bare hostnames) are skipped."""
        domains, _ = _parse_file("0.0.0.0 localmachine\n")
        assert len(domains) == 0

    def test_comment_lines_skipped(self):
        text = "# This is a comment\n! ABP comment\n0.0.0.0 ads.example.com\n"
        domains, _ = _parse_file(text)
        assert domains == {"ads.example.com"}

    def test_empty_lines_skipped(self):
        text = "\n\n0.0.0.0 ads.example.com\n\n"
        domains, _ = _parse_file(text)
        assert domains == {"ads.example.com"}

    def test_multiple_hosts(self):
        text = "0.0.0.0 one.com\n0.0.0.0 two.com\n127.0.0.1 three.com\n"
        domains, _ = _parse_file(text)
        assert domains == {"one.com", "two.com", "three.com"}

    def test_case_normalized(self):
        domains, _ = _parse_file("0.0.0.0 ADS.Example.COM\n")
        assert "ads.example.com" in domains


# ---------------------------------------------------------------------------
# Parsing: ABP domain format
# ---------------------------------------------------------------------------

class TestABPDomainFormat:
    def test_basic_abp_rule(self):
        domains, _ = _parse_file("||ads.example.com^\n")
        assert "ads.example.com" in domains

    def test_abp_rule_with_options(self):
        domains, _ = _parse_file("||tracker.example.com^$third-party\n")
        assert "tracker.example.com" in domains

    def test_abp_no_dot_excluded(self):
        domains, _ = _parse_file("||localhost^\n")
        assert len(domains) == 0

    def test_abp_case_normalized(self):
        domains, _ = _parse_file("||ADS.Example.COM^\n")
        assert "ads.example.com" in domains

    def test_mixed_formats(self):
        text = (
            "0.0.0.0 host-blocked.com\n"
            "||abp-blocked.com^\n"
            "# comment\n"
        )
        domains, _ = _parse_file(text)
        assert "host-blocked.com" in domains
        assert "abp-blocked.com" in domains


# ---------------------------------------------------------------------------
# Cosmetic selector extraction
# ---------------------------------------------------------------------------

class TestCosmeticSelectors:
    def test_generic_cosmetic_rule(self):
        _, cosmetic = _parse_file("##.ad-banner\n")
        assert ".ad-banner" in cosmetic

    def test_domain_specific_cosmetic_skipped(self):
        """Domain-qualified cosmetic rules (site.com##sel) are skipped."""
        _, cosmetic = _parse_file("example.com##.site-specific-ad\n")
        assert cosmetic == []

    def test_procedural_has_skipped(self):
        _, cosmetic = _parse_file("##div:has(.ad)\n")
        assert cosmetic == []

    def test_procedural_contains_skipped(self):
        _, cosmetic = _parse_file("##div:contains(Sponsored)\n")
        assert cosmetic == []

    def test_plus_prefix_skipped(self):
        _, cosmetic = _parse_file("##+js(something)\n")
        assert cosmetic == []

    def test_multiple_cosmetic_rules(self):
        text = "##.ad-one\n##.ad-two\n##.ad-three\n"
        _, cosmetic = _parse_file(text)
        assert cosmetic == [".ad-one", ".ad-two", ".ad-three"]

    def test_cosmetic_mixed_with_domains(self):
        text = "||blocked.com^\n##.hide-me\n0.0.0.0 other.com\n"
        domains, cosmetic = _parse_file(text)
        assert "blocked.com" in domains
        assert "other.com" in domains
        assert ".hide-me" in cosmetic


# ---------------------------------------------------------------------------
# get_cosmetic_css() output format
# ---------------------------------------------------------------------------

class TestGetCosmeticCSS:
    def setup_method(self):
        """Clear caches before each test to ensure isolation."""
        invalidate_parse_cache()

    def test_output_contains_display_none(self):
        css = get_cosmetic_css()
        # Even with no filter files, the hardcoded selectors produce output
        assert "display: none !important" in css

    def test_output_batches_selectors(self):
        css = get_cosmetic_css()
        # Each batch ends with { display: none !important; }
        lines = [l for l in css.split("\n") if l.strip()]
        for line in lines:
            assert line.endswith("{ display: none !important; }")

    def test_hardcoded_selectors_present(self):
        css = get_cosmetic_css()
        # A well-known cookie banner selector should appear
        assert "#cookie-banner" in css
        # A well-known ad selector should appear
        assert ".adsbygoogle" in css

    def test_batching_produces_multiple_rules(self):
        """With more than 50 hardcoded selectors, CSS should have multiple rule blocks."""
        rules = get_cosmetic_rules()
        css = get_cosmetic_css()
        lines = [l for l in css.split("\n") if l.strip()]
        # Number of batches should be ceil(len(rules) / 50)
        import math
        expected_batches = math.ceil(len(rules) / 50)
        assert len(lines) == expected_batches
        assert len(lines) > 1  # sanity: we have enough hardcoded rules for >1 batch


# ---------------------------------------------------------------------------
# Cosmetic CSS caching
# ---------------------------------------------------------------------------

class TestCosmeticCSSCaching:
    def setup_method(self):
        invalidate_parse_cache()

    def test_cache_is_used_on_second_call(self):
        first = get_cosmetic_css()
        # After the first call, the module-level cache should be populated
        assert filterlists._cosmetic_css_cache is not None
        second = get_cosmetic_css()
        # Should be the exact same object (identity, not just equality)
        assert first is second

    def test_invalidate_clears_cosmetic_cache(self):
        _ = get_cosmetic_css()
        assert filterlists._cosmetic_css_cache is not None
        invalidate_parse_cache()
        assert filterlists._cosmetic_css_cache is None

    def test_invalidate_specific_list_clears_cosmetic_cache(self):
        _ = get_cosmetic_css()
        assert filterlists._cosmetic_css_cache is not None
        invalidate_parse_cache("easylist")
        assert filterlists._cosmetic_css_cache is None

    def test_invalidate_clears_parse_cache(self):
        # Manually inject a fake entry into the parse cache
        filterlists._parse_cache["fake_list"] = ({"domain.com"}, [".sel"])
        invalidate_parse_cache()
        assert "fake_list" not in filterlists._parse_cache

    def test_invalidate_specific_list_removes_only_that_entry(self):
        filterlists._parse_cache["list_a"] = ({"a.com"}, [])
        filterlists._parse_cache["list_b"] = ({"b.com"}, [])
        invalidate_parse_cache("list_a")
        assert "list_a" not in filterlists._parse_cache
        assert "list_b" in filterlists._parse_cache
        # Clean up
        filterlists._parse_cache.clear()
