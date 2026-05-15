"""WARC/WACZ capture — record browsing sessions as replayable archives."""

import datetime
import hashlib
import io
import json
import os
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from . import storage


# ---------------------------------------------------------------------------
# WARC record helpers
# ---------------------------------------------------------------------------

def _warc_date() -> str:
    """Return current UTC timestamp in WARC-Date format."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _warc_record(record_type: str, target_uri: str, payload: bytes,
                 content_type: str = "application/http; msgtype=response",
                 warc_id: str | None = None) -> bytes:
    """Build a single WARC record."""
    warc_id = warc_id or f"<urn:uuid:{uuid.uuid4()}>"
    date = _warc_date()
    header_lines = [
        "WARC/1.1",
        f"WARC-Type: {record_type}",
        f"WARC-Date: {date}",
        f"WARC-Target-URI: {target_uri}",
        f"WARC-Record-ID: {warc_id}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(payload)}",
    ]
    header = "\r\n".join(header_lines) + "\r\n\r\n"
    return header.encode("utf-8") + payload + b"\r\n\r\n"


class WarcCapture:
    """Records browsing into WARC format."""

    def __init__(self):
        self._active = False
        self._records: list[bytes] = []
        self._urls: list[dict] = []  # CDX-like index entries
        self._start_url = ""
        self._start_time = 0.0

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self, url: str = ""):
        """Begin a new capture session."""
        self._active = True
        self._records = []
        self._urls = []
        self._start_url = url
        self._start_time = time.time()
        # Write warcinfo record
        info_payload = (
            f"software: Shroudbyte Browser\r\n"
            f"format: WARC/1.1\r\n"
            f"conformsTo: http://iipc.github.io/warc-specifications/\r\n"
        ).encode("utf-8")
        self._records.append(
            _warc_record("warcinfo", "", info_payload,
                         content_type="application/warc-fields")
        )

    def stop(self):
        """Stop the capture session."""
        self._active = False

    def add_page(self, url: str, title: str, html: str):
        """Record a page's HTML content as a WARC response record."""
        if not self._active:
            return
        payload = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(html.encode('utf-8'))}\r\n"
            f"\r\n"
            f"{html}"
        ).encode("utf-8")
        self._records.append(
            _warc_record("response", url, payload)
        )
        self._urls.append({
            "url": url,
            "title": title,
            "timestamp": _warc_date(),
        })

    def add_resource(self, url: str, content_type: str, data: bytes):
        """Record a sub-resource (image, CSS, JS, etc.)."""
        if not self._active:
            return
        payload = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(data)}\r\n"
            f"\r\n"
        ).encode("utf-8") + data
        self._records.append(
            _warc_record("resource", url, payload)
        )

    def save_warc(self, path: str | Path) -> Path:
        """Write all recorded data to a .warc file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            for record in self._records:
                f.write(record)
        return path

    def save_wacz(self, path: str | Path, title: str = "") -> Path:
        """Export as WACZ (Web Archive Collection Zipped) format."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        warc_data = b"".join(self._records)
        warc_hash = hashlib.sha256(warc_data).hexdigest()

        datapackage = {
            "profile": "data-package",
            "wacz_version": "1.1.1",
            "title": title or self._start_url,
            "mainPageUrl": self._start_url,
            "created": _warc_date(),
            "software": "Shroudbyte Browser",
            "pages": self._urls,
            "resources": [{
                "name": "data.warc",
                "path": "data.warc",
                "hash": f"sha256:{warc_hash}",
                "bytes": len(warc_data),
            }],
        }

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("datapackage.json", json.dumps(datapackage, indent=2))
            zf.writestr("data.warc", warc_data)

        return path

    def get_citation(self, url: str = "", title: str = "") -> dict:
        """Generate a citation bundle for the captured content."""
        warc_data = b"".join(self._records)
        return {
            "url": url or self._start_url,
            "title": title,
            "captured_at": _warc_date(),
            "archive_sha256": hashlib.sha256(warc_data).hexdigest(),
            "page_count": len(self._urls),
        }

    @property
    def record_count(self) -> int:
        return len(self._records)

    @property
    def page_count(self) -> int:
        return len(self._urls)

    @property
    def captured_urls(self) -> list[dict]:
        return list(self._urls)
