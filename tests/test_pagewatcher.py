"""Tests for browser.pagewatcher — text extraction, diff, and in-memory watches."""

from browser.pagewatcher import _extract_text, _compute_diff


class TestExtractText:
    """_extract_text converts HTML to plain text."""

    def test_basic_html(self):
        html = "<html><body><p>Hello world</p></body></html>"
        text = _extract_text(html)
        assert "Hello world" in text

    def test_strips_script_tags(self):
        html = "<html><body><script>var x = 1;</script><p>Visible</p></body></html>"
        text = _extract_text(html)
        assert "var x = 1" not in text
        assert "Visible" in text

    def test_strips_style_tags(self):
        html = "<html><body><style>body { color: red; }</style><p>Visible</p></body></html>"
        text = _extract_text(html)
        assert "color: red" not in text
        assert "Visible" in text

    def test_strips_noscript_and_svg(self):
        html = (
            "<html><body>"
            "<noscript>Enable JS</noscript>"
            "<svg><text>icon</text></svg>"
            "<p>Content</p>"
            "</body></html>"
        )
        text = _extract_text(html)
        assert "Enable JS" not in text
        assert "icon" not in text
        assert "Content" in text

    def test_empty_html(self):
        assert _extract_text("") == ""

    def test_nested_skip_tags(self):
        """Nested script inside style should still be skipped."""
        html = "<style><script>inner</script>outer</style><p>OK</p>"
        text = _extract_text(html)
        assert "inner" not in text
        assert "outer" not in text
        assert "OK" in text


class TestComputeDiff:
    """_compute_diff returns unified diff output."""

    def test_identical_texts(self):
        diff = _compute_diff("same\n", "same\n")
        assert diff == ""

    def test_changed_line(self):
        diff = _compute_diff("old line\n", "new line\n")
        assert "-old line" in diff
        assert "+new line" in diff

    def test_added_line(self):
        diff = _compute_diff("line1\n", "line1\nline2\n")
        assert "+line2" in diff

    def test_removed_line(self):
        diff = _compute_diff("line1\nline2\n", "line1\n")
        assert "-line2" in diff


class TestWatchesInMemory:
    """After _worker runs, watches are updated in-place (no storage reload)."""

    def test_worker_updates_watches_in_place(self, monkeypatch):
        """Mock storage so load_watches is only called at startup (start()),
        then verify _worker updates the in-memory list directly."""
        from unittest.mock import MagicMock, patch
        import time

        # We need to avoid instantiating the Qt QObject, so test the logic
        # by directly checking the _worker method's in-place update behavior.

        # Prepare a fake watch list
        watch = {
            "url": "https://example.com",
            "title": "Example",
            "interval": 3600,
            "enabled": True,
            "last_check": 0,
            "last_snapshot": "",
            "last_diff": "",
            "change_count": 0,
        }

        # Track how many times load_watches / update_watch are called
        load_count = 0
        original_load = None

        def counting_load():
            nonlocal load_count
            load_count += 1
            return [dict(watch)]

        # Patch storage before importing PageWatcher
        import browser.storage as st
        monkeypatch.setattr(st, "load_watches", counting_load)
        monkeypatch.setattr(st, "update_watch", lambda url, updates: None)

        # Now we can't easily create PageWatcher without Qt, so we verify
        # the design: _worker does w.update(updates) on self._watches
        # instead of calling reload_watches / load_watches.
        # We verify this by inspecting the source: _worker updates in-place.
        import inspect
        from browser.pagewatcher import PageWatcher
        source = inspect.getsource(PageWatcher._worker)

        # _worker should NOT call reload_watches or load_watches
        assert "reload_watches" not in source
        assert "load_watches" not in source

        # _worker SHOULD update the watch dict in-place
        assert "w.update(updates)" in source or "w.update(" in source
