"""Tests for browser.warc_capture — WARC record building and WACZ export."""

import hashlib
import json
import zipfile

import pytest

from browser.warc_capture import WarcCapture, _warc_record


class TestWarcRecord:
    def test_record_format(self):
        rec = _warc_record(
            "response",
            "https://example.com/",
            b"hello",
            content_type="text/plain",
        )
        head, _, body = rec.partition(b"\r\n\r\n")
        head = head.decode()
        assert head.startswith("WARC/1.1\r\n")
        assert "WARC-Type: response" in head
        assert "WARC-Target-URI: https://example.com/" in head
        assert "Content-Length: 5" in head
        assert body.startswith(b"hello")
        # Spec mandates a CRLFCRLF terminator after every record.
        assert rec.endswith(b"\r\n\r\n")


class TestCaptureLifecycle:
    def test_start_writes_warcinfo(self):
        c = WarcCapture()
        c.start("https://example.com/")
        # First record is always the warcinfo header.
        assert c.record_count == 1
        assert b"WARC-Type: warcinfo" in c._records[0]
        assert b"software: Shroudbyte" in c._records[0]
        assert c.is_active is True

    def test_inactive_capture_drops_records(self):
        c = WarcCapture()
        # No start() call.
        c.add_page("https://x", "T", "<html/>")
        c.add_resource("https://x/a.png", "image/png", b"\x89PNG")
        assert c.record_count == 0

    def test_stop_freezes_state(self):
        c = WarcCapture()
        c.start()
        c.add_page("https://x", "T", "<html/>")
        c.stop()
        # Inactive — further adds should be ignored.
        c.add_page("https://y", "Y", "<html/>")
        # warcinfo + the one page that landed before stop().
        assert c.record_count == 2
        assert c.is_active is False


class TestSaving:
    def test_save_warc_concatenates_records(self, tmp_path):
        c = WarcCapture()
        c.start()
        c.add_page("https://x", "X", "<p>hi</p>")
        out = c.save_warc(tmp_path / "out.warc")
        data = out.read_bytes()
        # Two records: warcinfo + response, with the page URL appearing
        # in the second one's Target-URI.
        assert b"WARC-Type: warcinfo" in data
        assert b"WARC-Type: response" in data
        assert b"https://x" in data
        assert b"<p>hi</p>" in data

    def test_save_wacz_is_zip_with_expected_members(self, tmp_path):
        c = WarcCapture()
        c.start("https://x/start")
        c.add_page("https://x", "X", "<p>hi</p>")
        out = c.save_wacz(tmp_path / "out.wacz", title="My capture")

        assert zipfile.is_zipfile(out)
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            assert {"datapackage.json", "data.warc"}.issubset(names)
            dp = json.loads(zf.read("datapackage.json"))
            warc_bytes = zf.read("data.warc")

        assert dp["title"] == "My capture"
        assert dp["mainPageUrl"] == "https://x/start"
        # Hash in datapackage must match the actual WARC payload.
        expected_hash = "sha256:" + hashlib.sha256(warc_bytes).hexdigest()
        assert dp["resources"][0]["hash"] == expected_hash
        assert dp["resources"][0]["bytes"] == len(warc_bytes)


class TestCitation:
    def test_citation_fields(self):
        c = WarcCapture()
        c.start("https://x/")
        c.add_page("https://x", "X", "<p>hi</p>")
        cite = c.get_citation(url="https://x", title="X")
        assert cite["url"] == "https://x"
        assert cite["title"] == "X"
        assert cite["page_count"] == 1
        # Hash is a 64-char hex digest.
        assert len(cite["archive_sha256"]) == 64
