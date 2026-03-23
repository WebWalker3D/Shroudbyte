"""Clipboard History — in-memory tracker for text copied during the session.

Records copied text directly from copy actions rather than monitoring
the system clipboard (which is unreliable with QtWebEngine on Linux).
Entirely in-memory — nothing touches disk, gone when the browser closes.
"""

import time

MAX_ENTRIES = 50
MAX_TEXT_LEN = 4096


class ClipboardHistory:
    """Tracks text copies during the browser session."""

    def __init__(self, get_current_url=None):
        self._entries: list[dict] = []
        self._get_url = get_current_url or (lambda: "")
        self._enabled = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def record(self, text: str, url: str = ""):
        """Record a copied text entry. Called directly from copy actions."""
        if not self._enabled or not text:
            return
        text = text[:MAX_TEXT_LEN]

        preview = text.strip().replace("\n", " ")
        if len(preview) > 80:
            preview = preview[:77] + "\u2026"

        entry = {
            "text": text,
            "url": url or self._get_url(),
            "time": time.time(),
            "preview": preview,
        }

        # Deduplicate: remove older entry with same text
        self._entries = [e for e in self._entries if e["text"] != text]
        self._entries.insert(0, entry)

        if len(self._entries) > MAX_ENTRIES:
            self._entries = self._entries[:MAX_ENTRIES]

    def get_history(self) -> list[dict]:
        return list(self._entries)

    def clear(self):
        self._entries.clear()
