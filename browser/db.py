"""SQLite database backend for high-traffic storage (history, screen time, etc.)."""

import json
import sqlite3
import threading
import time
from pathlib import Path

from . import storage as _storage  # for DATA_DIR


_SCHEMA_VERSION = 3

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS migrations (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    visited_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_url ON history(url);
CREATE INDEX IF NOT EXISTS idx_history_visited ON history(visited_at DESC);

CREATE TABLE IF NOT EXISTS screen_time (
    domain TEXT NOT NULL,
    date TEXT NOT NULL,
    seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (domain, date)
);

CREATE TABLE IF NOT EXISTS scroll_positions (
    url TEXT PRIMARY KEY,
    position REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS form_drafts (
    url TEXT PRIMARY KEY,
    fields_json TEXT NOT NULL,
    saved_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS permission_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host TEXT NOT NULL,
    feature TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_perm_usage_host ON permission_usage(host);
CREATE INDEX IF NOT EXISTS idx_perm_usage_ts ON permission_usage(timestamp DESC);

CREATE TABLE IF NOT EXISTS site_settings (
    host TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (host, key)
);
"""


class Database:
    """Thread-safe SQLite database for the browser."""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or (_storage.DATA_DIR / "shroudbyte.db")
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
                timeout=10,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
            self._apply_schema()
        return self._conn

    def _apply_schema(self):
        conn = self._conn
        conn.executescript(_SCHEMA_SQL)
        row = conn.execute(
            "SELECT MAX(version) as v FROM migrations"
        ).fetchone()
        current = row["v"] if row and row["v"] else 0
        if current < _SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO migrations (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )
            conn.commit()

    def close(self):
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def add_history_entry(self, title: str, url: str):
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO history (url, title, visited_at) VALUES (?, ?, ?)",
                (url, title, time.time()),
            )
            # Keep last 5000 entries
            conn.execute("""
                DELETE FROM history WHERE id NOT IN (
                    SELECT id FROM history ORDER BY visited_at DESC LIMIT 5000
                )
            """)
            conn.commit()

    def load_history(self) -> list[dict]:
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                "SELECT url, title, visited_at as visited FROM history ORDER BY visited_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_history(self):
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM history")
            conn.commit()

    def get_url_suggestions(self, limit: int = 500) -> list[tuple]:
        """Return (url, title, frequency) tuples sorted by visit count."""
        with self._lock:
            conn = self._connect()
            rows = conn.execute("""
                SELECT url, title, COUNT(*) as freq
                FROM history
                WHERE url NOT LIKE 'shroud:%'
                GROUP BY url
                ORDER BY freq DESC
                LIMIT ?
            """, (limit,)).fetchall()

            # Also merge bookmarks
            suggestions = {r["url"]: (r["title"], r["freq"]) for r in rows}

        # Merge bookmarks (outside lock to avoid JSON I/O under lock)
        for bm in _storage.load_bookmarks():
            url = bm.get("url", "")
            if not url:
                continue
            if url not in suggestions:
                suggestions[url] = (bm.get("title", ""), 0)
            elif not suggestions[url][0]:
                suggestions[url] = (bm.get("title", ""), suggestions[url][1])

        result = [(url, title, freq) for url, (title, freq) in suggestions.items()]
        result.sort(key=lambda t: t[2], reverse=True)
        return result[:limit]

    # ------------------------------------------------------------------
    # Screen time
    # ------------------------------------------------------------------

    def add_screen_time(self, domain: str, date_str: str, seconds: int):
        with self._lock:
            conn = self._connect()
            conn.execute("""
                INSERT INTO screen_time (domain, date, seconds) VALUES (?, ?, ?)
                ON CONFLICT(domain, date) DO UPDATE SET seconds = seconds + excluded.seconds
            """, (domain, date_str, seconds))
            conn.commit()

    def add_screen_time_batch(self, entries: dict[str, int], date_str: str):
        """Flush multiple domain -> seconds entries at once."""
        with self._lock:
            conn = self._connect()
            for domain, seconds in entries.items():
                conn.execute("""
                    INSERT INTO screen_time (domain, date, seconds) VALUES (?, ?, ?)
                    ON CONFLICT(domain, date) DO UPDATE SET seconds = seconds + excluded.seconds
                """, (domain, date_str, seconds))
            conn.commit()

    def load_screen_time(self) -> dict:
        """Return {domain: {date: seconds}} dict."""
        with self._lock:
            conn = self._connect()
            rows = conn.execute("SELECT domain, date, seconds FROM screen_time").fetchall()
        result: dict = {}
        for r in rows:
            if r["domain"] not in result:
                result[r["domain"]] = {}
            result[r["domain"]][r["date"]] = r["seconds"]
        return result

    def clear_screen_time(self):
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM screen_time")
            conn.commit()

    # ------------------------------------------------------------------
    # Scroll positions
    # ------------------------------------------------------------------

    def get_scroll_position(self, url: str) -> float:
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT position FROM scroll_positions WHERE url = ?", (url,)
            ).fetchone()
            return row["position"] if row else 0.0

    def set_scroll_position(self, url: str, position: float):
        with self._lock:
            conn = self._connect()
            if position < 0.01:
                conn.execute("DELETE FROM scroll_positions WHERE url = ?", (url,))
            else:
                conn.execute("""
                    INSERT OR REPLACE INTO scroll_positions (url, position, updated_at)
                    VALUES (?, ?, ?)
                """, (url, round(position, 4), time.time()))
                # LRU eviction
                conn.execute("""
                    DELETE FROM scroll_positions WHERE url NOT IN (
                        SELECT url FROM scroll_positions ORDER BY updated_at DESC LIMIT 2000
                    )
                """)
            conn.commit()

    # ------------------------------------------------------------------
    # Form drafts
    # ------------------------------------------------------------------

    def get_form_draft(self, url: str) -> dict | None:
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT fields_json, saved_at FROM form_drafts WHERE url = ?", (url,)
            ).fetchone()
            if row:
                return {"fields": json.loads(row["fields_json"]), "saved": row["saved_at"]}
            return None

    def save_form_draft(self, url: str, fields: dict, timestamp: float | None = None):
        ts = timestamp or time.time()
        with self._lock:
            conn = self._connect()
            conn.execute("""
                INSERT OR REPLACE INTO form_drafts (url, fields_json, saved_at)
                VALUES (?, ?, ?)
            """, (url, json.dumps(fields, separators=(',', ':')), ts))
            # LRU eviction
            conn.execute("""
                DELETE FROM form_drafts WHERE url NOT IN (
                    SELECT url FROM form_drafts ORDER BY saved_at DESC LIMIT 200
                )
            """)
            conn.commit()

    def remove_form_draft(self, url: str):
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM form_drafts WHERE url = ?", (url,))
            conn.commit()

    # ------------------------------------------------------------------
    # Permission usage ledger
    # ------------------------------------------------------------------

    def log_permission_usage(self, host: str, feature: str, action: str):
        """Insert a permission usage event."""
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO permission_usage (host, feature, action, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (host, feature, action, time.time()),
            )
            # Keep last 10 000 entries
            conn.execute("""
                DELETE FROM permission_usage WHERE id NOT IN (
                    SELECT id FROM permission_usage ORDER BY timestamp DESC LIMIT 10000
                )
            """)
            conn.commit()

    def get_permission_usage(self, host: str | None = None,
                             limit: int = 500) -> list[dict]:
        """Return recent permission usage events, optionally filtered by host."""
        with self._lock:
            conn = self._connect()
            if host:
                rows = conn.execute(
                    "SELECT host, feature, action, timestamp FROM permission_usage "
                    "WHERE host = ? ORDER BY timestamp DESC LIMIT ?",
                    (host, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT host, feature, action, timestamp FROM permission_usage "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_permission_anomalies(self, threshold: int = 10,
                                 hours: int = 1) -> list[dict]:
        """Detect host+feature combos exceeding *threshold* uses in *hours*."""
        cutoff = time.time() - (hours * 3600)
        with self._lock:
            conn = self._connect()
            rows = conn.execute("""
                SELECT host, feature, COUNT(*) as cnt
                FROM permission_usage
                WHERE timestamp >= ?
                GROUP BY host, feature
                HAVING cnt > ?
                ORDER BY cnt DESC
            """, (cutoff, threshold)).fetchall()
            return [dict(r) for r in rows]

    def export_permission_log(self, path: str, host: str | None = None,
                              fmt: str = "csv"):
        """Export the permission usage log to a CSV file."""
        import csv as _csv
        entries = self.get_permission_usage(host, limit=10000)
        with open(path, "w", newline="") as f:
            writer = _csv.DictWriter(
                f, fieldnames=["host", "feature", "action", "timestamp"],
            )
            writer.writeheader()
            writer.writerows(entries)

    # ------------------------------------------------------------------
    # Per-site settings
    # ------------------------------------------------------------------

    def get_site_settings(self, host: str) -> dict:
        """Return per-site overrides as a dict."""
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                "SELECT key, value FROM site_settings WHERE host = ?", (host,)
            ).fetchall()
        result = {}
        for r in rows:
            val = r["value"]
            # Coerce stored strings back to correct types
            if val == "true":
                result[r["key"]] = True
            elif val == "false":
                result[r["key"]] = False
            else:
                result[r["key"]] = val
        return result

    def set_site_setting(self, host: str, key: str, value):
        """Set a single per-site setting."""
        str_val = str(value).lower() if isinstance(value, bool) else str(value)
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT OR REPLACE INTO site_settings (host, key, value) VALUES (?, ?, ?)",
                (host, key, str_val),
            )
            conn.commit()

    def remove_site_settings(self, host: str):
        """Remove all per-site overrides for a host."""
        with self._lock:
            conn = self._connect()
            conn.execute("DELETE FROM site_settings WHERE host = ?", (host,))
            conn.commit()

    def get_customized_hosts(self) -> list[str]:
        """Return hosts that have per-site overrides."""
        with self._lock:
            conn = self._connect()
            rows = conn.execute("SELECT DISTINCT host FROM site_settings ORDER BY host").fetchall()
        return [r["host"] for r in rows]

    # ------------------------------------------------------------------
    # Migration from JSON files
    # ------------------------------------------------------------------

    def migrate_from_json(self):
        """One-time migration of JSON data to SQLite."""
        data_dir = _storage.DATA_DIR

        # History
        hist_path = data_dir / "history.json"
        if hist_path.exists():
            try:
                with open(hist_path) as f:
                    entries = json.load(f)
                with self._lock:
                    conn = self._connect()
                    for entry in entries:
                        conn.execute(
                            "INSERT INTO history (url, title, visited_at) VALUES (?, ?, ?)",
                            (entry.get("url", ""), entry.get("title", ""),
                             entry.get("visited", 0)),
                        )
                    conn.commit()
                hist_path.rename(hist_path.with_suffix(".json.migrated"))
            except Exception:
                pass  # Don't block startup on migration failure

        # Screen time
        st_path = data_dir / "screen_time.json"
        if st_path.exists():
            try:
                with open(st_path) as f:
                    data = json.load(f)
                with self._lock:
                    conn = self._connect()
                    for domain, dates in data.items():
                        for date_str, seconds in dates.items():
                            conn.execute("""
                                INSERT OR REPLACE INTO screen_time (domain, date, seconds)
                                VALUES (?, ?, ?)
                            """, (domain, date_str, seconds))
                    conn.commit()
                st_path.rename(st_path.with_suffix(".json.migrated"))
            except Exception:
                pass

        # Scroll positions
        sp_path = data_dir / "scroll_positions.json"
        if sp_path.exists():
            try:
                with open(sp_path) as f:
                    data = json.load(f)
                with self._lock:
                    conn = self._connect()
                    for url, pos in data.items():
                        conn.execute("""
                            INSERT OR REPLACE INTO scroll_positions (url, position, updated_at)
                            VALUES (?, ?, ?)
                        """, (url, pos, time.time()))
                    conn.commit()
                sp_path.rename(sp_path.with_suffix(".json.migrated"))
            except Exception:
                pass

        # Form drafts
        fd_path = data_dir / "form_drafts.json"
        if fd_path.exists():
            try:
                with open(fd_path) as f:
                    data = json.load(f)
                with self._lock:
                    conn = self._connect()
                    for url, draft in data.items():
                        conn.execute("""
                            INSERT OR REPLACE INTO form_drafts (url, fields_json, saved_at)
                            VALUES (?, ?, ?)
                        """, (url, json.dumps(draft.get("fields", {})),
                              draft.get("saved", time.time())))
                    conn.commit()
                fd_path.rename(fd_path.with_suffix(".json.migrated"))
            except Exception:
                pass


# Singleton instance
_db: Database | None = None


def get_db() -> Database:
    """Return the shared Database singleton."""
    global _db
    if _db is None:
        _db = Database()
        _db.migrate_from_json()
    return _db
