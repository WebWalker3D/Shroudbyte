"""Page Watch — periodic background page change monitoring.

Fetches watched pages via HTTP GET in background threads, extracts visible
text, diffs against the previous snapshot, and emits a signal when
meaningful content changes are detected.
"""

import difflib
import html.parser
import ssl
import threading
import time
import urllib.request

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from . import storage

MIN_CHANGE_CHARS = 10  # ignore changes smaller than this


# ── HTML → plain text ────────────────────────────────────────────

class _TextExtractor(html.parser.HTMLParser):
    """Extract visible text from HTML, ignoring scripts/styles."""

    _SKIP = frozenset({"script", "style", "noscript", "svg", "math", "head"})

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._SKIP:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._skip == 0:
            self._parts.append(data)

    def get_text(self):
        return " ".join(self._parts)


def _extract_text(html_content: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html_content)
    except Exception:
        pass
    return p.get_text()


def _compute_diff(old: str, new: str) -> str:
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="previous", tofile="current", lineterm="\n",
    ))


# ── watcher engine ───────────────────────────────────────────────

class PageWatcher(QObject):
    """Monitors watched pages for changes in background threads."""

    page_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._watches: list[dict] = []
        self._lock = threading.Lock()
        self._checking: set[str] = set()

    def start(self):
        self._watches = storage.load_watches()
        self._timer.start(60_000)  # poll every 60 s to see what's due

    def stop(self):
        self._timer.stop()

    def reload_watches(self):
        self._watches = storage.load_watches()

    def check_now(self, url: str):
        """Force an immediate check for a specific URL."""
        for w in self._watches:
            if w["url"] == url:
                self._spawn(w)
                break

    # ── internals ────────────────────────────────────────────────

    def _tick(self):
        now = time.time()
        for w in self._watches:
            if not w.get("enabled", True):
                continue
            if w["url"] in self._checking:
                continue
            if now - w.get("last_check", 0) >= w.get("interval", 3600):
                self._spawn(w)

    def _spawn(self, watch):
        with self._lock:
            if watch["url"] in self._checking:
                return
            self._checking.add(watch["url"])
        threading.Thread(target=self._worker, args=(dict(watch),), daemon=True).start()

    def _worker(self, watch):
        try:
            html_content = self._fetch(watch["url"])
            new_text = _extract_text(html_content)
            old_text = watch.get("last_snapshot", "")

            changed = False
            diff = ""

            if old_text and new_text:
                old_norm = " ".join(old_text.split())
                new_norm = " ".join(new_text.split())
                if old_norm != new_norm and abs(len(new_norm) - len(old_norm)) >= MIN_CHANGE_CHARS:
                    changed = True
                    diff = _compute_diff(old_text, new_text)

            updates: dict = {
                "last_check": time.time(),
                "last_snapshot": new_text,
            }
            if changed:
                updates["last_changed"] = time.time()
                updates["last_diff"] = diff
                updates["change_count"] = watch.get("change_count", 0) + 1

            storage.update_watch(watch["url"], updates)
            self._watches = storage.load_watches()

            if changed:
                for w in self._watches:
                    if w["url"] == watch["url"]:
                        self.page_changed.emit(dict(w))
                        break
        except Exception:
            # Network errors, timeouts, encoding issues — all expected
            pass
        finally:
            with self._lock:
                self._checking.discard(watch["url"])

    @staticmethod
    def _fetch(url: str) -> str:
        req = urllib.request.Request(url, headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        })
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
