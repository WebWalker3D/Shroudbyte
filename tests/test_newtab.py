"""Tests for browser.newtab — daily quote / wallpaper / page generation."""

import base64
import datetime

import pytest

from browser import newtab, storage


class TestDailyQuote:
    def test_returns_tuple_of_strings(self):
        text, author = newtab._daily_quote()
        assert isinstance(text, str) and text
        assert isinstance(author, str) and author

    def test_same_day_same_quote(self):
        a = newtab._daily_quote()
        b = newtab._daily_quote()
        assert a == b

    def test_index_in_range(self, monkeypatch):
        # Try a handful of days; every result must come from _QUOTES.
        for ordinal in range(700000, 700050):
            class FakeDate:
                @staticmethod
                def today():
                    class D:
                        @staticmethod
                        def toordinal():
                            return ordinal
                    return D()
            monkeypatch.setattr(newtab.datetime, "date", FakeDate)
            assert newtab._daily_quote() in newtab._QUOTES


class TestWallpaper:
    def test_no_path_returns_empty(self):
        assert newtab._wallpaper_data_url({}) == ""

    def test_missing_file_returns_empty(self, tmp_path):
        assert newtab._wallpaper_data_url(
            {"wallpaper": str(tmp_path / "nope.png")}
        ) == ""

    def test_png_detection(self, tmp_path):
        png = tmp_path / "w.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        url = newtab._wallpaper_data_url({"wallpaper": str(png)})
        assert url.startswith("data:image/png;base64,")

    def test_jpeg_detection(self, tmp_path):
        jpg = tmp_path / "w.jpg"
        jpg.write_bytes(b"\xff\xd8\xff" + b"\x00" * 32)
        url = newtab._wallpaper_data_url({"wallpaper": str(jpg)})
        assert url.startswith("data:image/jpeg;base64,")

    def test_round_trip_payload(self, tmp_path):
        # Body bytes of the data URL must round-trip back to the file.
        png = tmp_path / "w.png"
        body = b"\x89PNG\r\n\x1a\n" + b"some-payload-bytes"
        png.write_bytes(body)
        url = newtab._wallpaper_data_url({"wallpaper": str(png)})
        b64 = url.split(",", 1)[1]
        assert base64.b64decode(b64) == body


class TestGenerateNewTabHtml:
    def test_returns_html(self, tmp_data_dir):
        html = newtab.generate_new_tab_html()
        assert html.lstrip().startswith("<!DOCTYPE")
        assert "<html" in html

    def test_uses_configured_search_engine(self, tmp_data_dir):
        storage.save_settings({
            "search_engine": "https://kagi.com/search?q={}",
        })
        html = newtab.generate_new_tab_html()
        assert "kagi.com" in html

    def test_includes_bookmarks(self, tmp_data_dir):
        storage.add_bookmark("My Site", "https://my-special-site.example")
        html = newtab.generate_new_tab_html()
        assert "my-special-site.example" in html or "My Site" in html

    @pytest.mark.parametrize("hour,greeting", [
        (8, "morning"),
        (14, "afternoon"),
        (19, "evening"),
        (2, "night"),
    ])
    def test_time_based_greeting(self, tmp_data_dir, monkeypatch, hour, greeting):
        class FakeDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 1, 1, hour, 0, 0)
        monkeypatch.setattr(newtab.datetime, "datetime", FakeDateTime)
        html = newtab.generate_new_tab_html().lower()
        assert greeting in html
