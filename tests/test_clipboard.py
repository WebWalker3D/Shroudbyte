"""Tests for browser.clipboard_history — ClipboardHistory."""

from browser.clipboard_history import ClipboardHistory, MAX_ENTRIES, MAX_TEXT_LEN


class TestRecordAndGetHistory:
    """Basic record / retrieve / clear operations."""

    def test_record_and_get(self):
        ch = ClipboardHistory()
        ch.record("hello")
        history = ch.get_history()
        assert len(history) == 1
        assert history[0]["text"] == "hello"

    def test_get_history_returns_copy(self):
        ch = ClipboardHistory()
        ch.record("a")
        h1 = ch.get_history()
        h1.clear()
        assert len(ch.get_history()) == 1  # internal list unaffected

    def test_record_with_url(self):
        ch = ClipboardHistory()
        ch.record("text", url="https://example.com")
        assert ch.get_history()[0]["url"] == "https://example.com"

    def test_record_uses_get_current_url(self):
        ch = ClipboardHistory(get_current_url=lambda: "https://auto.com")
        ch.record("text")
        assert ch.get_history()[0]["url"] == "https://auto.com"

    def test_clear(self):
        ch = ClipboardHistory()
        ch.record("a")
        ch.record("b")
        ch.clear()
        assert ch.get_history() == []

    def test_record_empty_string_ignored(self):
        ch = ClipboardHistory()
        ch.record("")
        assert ch.get_history() == []

    def test_record_when_disabled(self):
        ch = ClipboardHistory()
        ch.set_enabled(False)
        ch.record("should not appear")
        assert ch.get_history() == []

    def test_newest_first(self):
        ch = ClipboardHistory()
        ch.record("first")
        ch.record("second")
        history = ch.get_history()
        assert history[0]["text"] == "second"
        assert history[1]["text"] == "first"


class TestDeduplication:
    """Recording the same text again should remove the older entry."""

    def test_duplicate_text_moves_to_top(self):
        ch = ClipboardHistory()
        ch.record("alpha")
        ch.record("beta")
        ch.record("alpha")  # duplicate
        history = ch.get_history()
        assert len(history) == 2
        assert history[0]["text"] == "alpha"
        assert history[1]["text"] == "beta"


class TestMaxHistorySize:
    """History should be capped at MAX_ENTRIES."""

    def test_cap_at_max_entries(self):
        ch = ClipboardHistory()
        for i in range(MAX_ENTRIES + 20):
            ch.record(f"entry-{i}")
        assert len(ch.get_history()) == MAX_ENTRIES
        # Most recent entry should be at the top
        assert ch.get_history()[0]["text"] == f"entry-{MAX_ENTRIES + 19}"

    def test_text_truncated_to_max_len(self):
        ch = ClipboardHistory()
        long_text = "x" * (MAX_TEXT_LEN + 500)
        ch.record(long_text)
        assert len(ch.get_history()[0]["text"]) == MAX_TEXT_LEN


class TestPreview:
    """The preview field should be a short, single-line summary."""

    def test_preview_truncates_long_text(self):
        ch = ClipboardHistory()
        ch.record("a" * 200)
        preview = ch.get_history()[0]["preview"]
        assert len(preview) <= 80

    def test_preview_collapses_newlines(self):
        ch = ClipboardHistory()
        ch.record("line1\nline2\nline3")
        preview = ch.get_history()[0]["preview"]
        assert "\n" not in preview
