"""Tests for browser.reader — reader-mode HTML generation + extractor JS shape."""

from browser.reader import READER_EXTRACT_JS, generate_reader_html


class TestExtractJs:
    def test_is_iife(self):
        js = READER_EXTRACT_JS.strip()
        # The extractor runs in the page's global scope; the IIFE wrapper
        # prevents leaking locals like `candidates` / `title` into window.
        assert js.startswith("(function()") or js.startswith("(function ()")
        assert js.rstrip(";").endswith("})()") or js.endswith("})();")

    def test_covers_metadata_sources(self):
        # Must look at OpenGraph, Twitter, and document.title as fallbacks.
        for needle in ("og:title", "twitter:title", "document.title"):
            assert needle in READER_EXTRACT_JS

    def test_byline_extraction_paths(self):
        for needle in ("author", "article:author", "byline"):
            assert needle in READER_EXTRACT_JS


class TestGenerateReaderHtml:
    def test_basic_render(self):
        html = generate_reader_html(
            title="Hello",
            byline="By Someone",
            content="<p>Body paragraph.</p>",
            site_name="example.com",
            original_url="https://example.com/article",
        )
        assert "Hello" not in html.split("<style>")[0]  # title styled, not in <head>
        # The body markup must appear verbatim.
        assert "<p>Body paragraph.</p>" in html
        assert "example.com" in html
        assert 'href="https://example.com/article"' in html

    def test_missing_byline_omits_div(self):
        html = generate_reader_html(
            title="t", byline="", content="<p>x</p>",
            site_name="s", original_url="https://s",
        )
        assert 'class="byline"' not in html

    def test_includes_doctype_and_html_skeleton(self):
        html = generate_reader_html("t", "", "<p>x</p>", "s", "https://s")
        assert html.lstrip().startswith("<!DOCTYPE html>")
        assert "<html>" in html and "</html>" in html
        assert "<style>" in html
