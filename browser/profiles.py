"""Browser profiles — separate cookie jars and storage per container."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtWebEngineCore import QWebEngineProfile

from . import storage


@dataclass
class BrowserProfile:
    """Represents a browser container/profile."""
    name: str
    color: str  # hex color for tab indicator
    qt_profile: QWebEngineProfile | None = None
    auto_assign: list[str] = field(default_factory=list)  # domain patterns


_DEFAULT_PROFILES = [
    {"name": "Default", "color": "#6366f1", "auto_assign": []},
    {"name": "Work", "color": "#22c55e", "auto_assign": []},
    {"name": "Shopping", "color": "#f59e0b", "auto_assign": []},
    {"name": "Banking", "color": "#ef4444", "auto_assign": []},
]


class ProfileManager:
    """Manages browser profiles/containers."""

    def __init__(self, parent=None):
        self._parent = parent
        self._profiles: dict[str, BrowserProfile] = {}
        self._load_profiles()

    def _load_profiles(self):
        """Load profile definitions from storage."""
        # _load_json normalises a missing file to [], not None, so we
        # treat "no entries on disk" the same as "first run" and seed.
        saved = storage._load_json("profiles.json", [])
        if not saved:
            saved = _DEFAULT_PROFILES
            storage._save_json("profiles.json", saved)

        for pdata in saved:
            name = pdata["name"]
            profile = BrowserProfile(
                name=name,
                color=pdata.get("color", "#6366f1"),
                auto_assign=pdata.get("auto_assign", []),
            )
            self._profiles[name] = profile

    def _save_profiles(self):
        """Persist profile definitions."""
        data = []
        for p in self._profiles.values():
            data.append({
                "name": p.name,
                "color": p.color,
                "auto_assign": p.auto_assign,
            })
        storage._save_json("profiles.json", data)

    def get_qt_profile(self, name: str) -> QWebEngineProfile:
        """Get or create a QWebEngineProfile for the named profile."""
        if name not in self._profiles:
            name = "Default"
        profile = self._profiles[name]
        if profile.qt_profile is None:
            profile_dir = str(storage.DATA_DIR / "profiles" / name / "webengine")
            cache_dir = str(storage.DATA_DIR / "profiles" / name / "cache")
            os.makedirs(profile_dir, exist_ok=True)
            os.makedirs(cache_dir, exist_ok=True)

            qt_prof = QWebEngineProfile(f"shroud_{name}", self._parent)
            qt_prof.setPersistentStoragePath(profile_dir)
            qt_prof.setCachePath(cache_dir)
            qt_prof.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
            )
            profile.qt_profile = qt_prof
        return profile.qt_profile

    def get_profile(self, name: str) -> BrowserProfile | None:
        """Get profile by name."""
        return self._profiles.get(name)

    def list_profiles(self) -> list[BrowserProfile]:
        """Return all profiles."""
        return list(self._profiles.values())

    def add_profile(self, name: str, color: str = "#6366f1", auto_assign: list[str] | None = None):
        """Create a new profile."""
        if name in self._profiles:
            return False
        self._profiles[name] = BrowserProfile(
            name=name, color=color, auto_assign=auto_assign or [],
        )
        self._save_profiles()
        return True

    def remove_profile(self, name: str):
        """Remove a profile (cannot remove Default)."""
        if name == "Default" or name not in self._profiles:
            return False
        p = self._profiles.pop(name)
        if p.qt_profile:
            p.qt_profile.deleteLater()
        self._save_profiles()
        return True

    def update_profile(self, name: str, color: str | None = None, auto_assign: list[str] | None = None):
        """Update profile color or auto-assign rules."""
        p = self._profiles.get(name)
        if not p:
            return
        if color is not None:
            p.color = color
        if auto_assign is not None:
            p.auto_assign = auto_assign
        self._save_profiles()

    def match_profile_for_url(self, url: str) -> str:
        """Return the profile name that should be used for a URL, based on auto-assign rules."""
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        for name, profile in self._profiles.items():
            for pattern in profile.auto_assign:
                if host == pattern or host.endswith('.' + pattern):
                    return name
        return "Default"

    @property
    def default_profile(self) -> BrowserProfile:
        return self._profiles.get("Default", list(self._profiles.values())[0])
