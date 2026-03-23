"""Named session management — save, load, and manage named browsing sessions."""

import time
from . import storage
from .db import get_db


def save_named_session(name: str, tabs: list[dict]):
    """Save a named session (list of tab dicts)."""
    db = get_db()
    db._connect()  # ensure DB ready
    # Store in a simple JSON file keyed by name
    sessions = storage._load_json("named_sessions.json", {})
    sessions[name] = {
        "tabs": tabs,
        "created_at": sessions.get(name, {}).get("created_at", time.time()),
        "updated_at": time.time(),
    }
    storage._save_json("named_sessions.json", sessions)


def load_named_session(name: str) -> list[dict]:
    """Load tabs from a named session."""
    sessions = storage._load_json("named_sessions.json", {})
    entry = sessions.get(name, {})
    return entry.get("tabs", [])


def list_sessions() -> list[dict]:
    """Return list of {name, tab_count, created_at, updated_at}."""
    sessions = storage._load_json("named_sessions.json", {})
    result = []
    for name, data in sessions.items():
        result.append({
            "name": name,
            "tab_count": len(data.get("tabs", [])),
            "created_at": data.get("created_at", 0),
            "updated_at": data.get("updated_at", 0),
        })
    result.sort(key=lambda s: s["updated_at"], reverse=True)
    return result


def delete_session(name: str):
    """Delete a named session."""
    sessions = storage._load_json("named_sessions.json", {})
    sessions.pop(name, None)
    storage._save_json("named_sessions.json", sessions)
