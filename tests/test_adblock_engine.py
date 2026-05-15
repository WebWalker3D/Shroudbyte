"""Tests for browser.adblock_engine — ABP filter engine."""

import pytest

from browser.adblock_engine import AdBlockEngine


@pytest.fixture
def engine():
    return AdBlockEngine()


class TestDomainAnchor:
    def test_blocks_anchor_match(self, engine):
        engine.parse_rules(["||ads.example.com^"])
        assert engine.should_block("https://ads.example.com/banner.gif") is True

    def test_does_not_block_other_domains(self, engine):
        engine.parse_rules(["||ads.example.com^"])
        assert engine.should_block("https://example.com/index.html") is False

    def test_blocks_subdomain(self, engine):
        engine.parse_rules(["||ads.example.com^"])
        assert engine.should_block("https://tracker.ads.example.com/x") is True


class TestExceptions:
    def test_exception_overrides_block(self, engine):
        engine.parse_rules([
            "||ads.example.com^",
            "@@||ads.example.com/safe.js",
        ])
        assert engine.should_block("https://ads.example.com/banner.gif") is True
        assert engine.should_block("https://ads.example.com/safe.js") is False


class TestThirdPartyOption:
    def test_third_party_only(self, engine):
        engine.parse_rules(["||tracker.com^$third-party"])
        # Loaded from same origin — first-party, not blocked.
        assert engine.should_block(
            "https://tracker.com/x.js",
            source_url="https://tracker.com/page",
        ) is False
        # Loaded from a different origin — third-party, blocked.
        assert engine.should_block(
            "https://tracker.com/x.js",
            source_url="https://news.example/page",
        ) is True


class TestResourceType:
    def test_script_only_blocks_scripts(self, engine):
        engine.parse_rules(["||badcdn.com^$script"])
        assert engine.should_block(
            "https://badcdn.com/x.js",
            source_url="https://site.example/",
            resource_type="script",
        ) is True
        assert engine.should_block(
            "https://badcdn.com/img.png",
            source_url="https://site.example/",
            resource_type="image",
        ) is False


class TestDomainOption:
    def test_include_list(self, engine):
        engine.parse_rules(["||ads.com^$domain=news.example|sports.example"])
        # On news.example — block.
        assert engine.should_block(
            "https://ads.com/x", source_url="https://news.example/page"
        ) is True
        # On unrelated site — don't block.
        assert engine.should_block(
            "https://ads.com/x", source_url="https://recipes.example/page"
        ) is False

    def test_exclude_pattern(self, engine):
        engine.parse_rules([
            "||ads.com^$domain=~trusted.example",
        ])
        # On trusted.example — excluded, don't block.
        assert engine.should_block(
            "https://ads.com/x", source_url="https://trusted.example/page"
        ) is False


class TestDynamicRules:
    def test_block_action(self, engine):
        engine.set_dynamic_rule("news.example", "tracker.com", "block")
        assert engine.should_block(
            "https://tracker.com/x",
            source_url="https://news.example/page",
        ) is True

    def test_allow_action_doesnt_force_block(self, engine):
        engine.set_dynamic_rule("news.example", "tracker.com", "allow")
        assert engine.should_block(
            "https://tracker.com/x",
            source_url="https://news.example/page",
        ) is False

    def test_remove_dynamic_rule(self, engine):
        engine.set_dynamic_rule("news.example", "tracker.com", "block")
        engine.remove_dynamic_rule("news.example", "tracker.com")
        assert engine.get_dynamic_rules("news.example") == {}


class TestComments:
    def test_comments_and_headers_ignored(self, engine):
        engine.parse_rules([
            "! This is a comment",
            "[Adblock Plus 2.0]",
            "||ads.example.com^",
        ])
        # Only the real rule applied.
        assert engine.should_block("https://ads.example.com/x") is True
        # The comment must NOT have been compiled and matched.
        assert engine.should_block("https://example.com/comment") is False


class TestThirdPartyDetection:
    def test_subdomain_is_first_party(self):
        assert AdBlockEngine._is_third_party(
            "https://cdn.example.com/", "https://example.com/"
        ) is False

    def test_different_etld_is_third_party(self):
        assert AdBlockEngine._is_third_party(
            "https://tracker.net/", "https://example.com/"
        ) is True

    def test_no_source_is_first_party(self):
        # No referrer = treat as first-party so we don't over-block.
        assert AdBlockEngine._is_third_party("https://anything/", "") is False
