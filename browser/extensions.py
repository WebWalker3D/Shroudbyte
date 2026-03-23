"""Minimal content script extension system.

Supports simple extensions that inject JavaScript into web pages.
Each extension is a directory under ~/.shroudbyte/extensions/ containing:
  - manifest.json: {name, version, description, content_scripts: [{matches: [...], js: [...], css: [...]}]}
  - *.js and *.css files referenced in the manifest
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from fnmatch import fnmatch

from . import storage


@dataclass
class ContentScript:
    """A content script definition from a manifest."""
    matches: list[str] = field(default_factory=list)  # URL patterns like "*://*.example.com/*"
    js: list[str] = field(default_factory=list)  # JS file paths relative to extension dir
    css: list[str] = field(default_factory=list)  # CSS file paths
    run_at: str = "document_idle"  # document_start, document_end, document_idle


@dataclass
class Extension:
    """A loaded extension."""
    name: str
    version: str
    description: str
    path: Path
    enabled: bool = True
    content_scripts: list[ContentScript] = field(default_factory=list)


class ExtensionManager:
    """Manages content script extensions."""

    def __init__(self):
        self._extensions_dir = storage.DATA_DIR / "extensions"
        self._extensions: dict[str, Extension] = {}
        self._load_extensions()

    def _load_extensions(self):
        """Scan extensions directory and load manifests."""
        if not self._extensions_dir.exists():
            self._extensions_dir.mkdir(parents=True, exist_ok=True)
            return

        # Load enabled/disabled state
        state = storage._load_json("extension_state.json", {})

        for entry in self._extensions_dir.iterdir():
            if not entry.is_dir():
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)

                ext = Extension(
                    name=manifest.get("name", entry.name),
                    version=manifest.get("version", "0.0.0"),
                    description=manifest.get("description", ""),
                    path=entry,
                    enabled=state.get(entry.name, True),
                )

                for cs_data in manifest.get("content_scripts", []):
                    cs = ContentScript(
                        matches=cs_data.get("matches", []),
                        js=cs_data.get("js", []),
                        css=cs_data.get("css", []),
                        run_at=cs_data.get("run_at", "document_idle"),
                    )
                    ext.content_scripts.append(cs)

                self._extensions[entry.name] = ext
            except (json.JSONDecodeError, KeyError):
                continue

    def reload(self):
        """Re-scan extensions directory."""
        self._extensions.clear()
        self._load_extensions()

    def get_extensions(self) -> list[Extension]:
        """Return all loaded extensions."""
        return list(self._extensions.values())

    def enable(self, name: str):
        """Enable an extension."""
        if name in self._extensions:
            self._extensions[name].enabled = True
            self._save_state()

    def disable(self, name: str):
        """Disable an extension."""
        if name in self._extensions:
            self._extensions[name].enabled = False
            self._save_state()

    def _save_state(self):
        """Persist enabled/disabled state."""
        state = {name: ext.enabled for name, ext in self._extensions.items()}
        storage._save_json("extension_state.json", state)

    def get_scripts_for_url(self, url: str, run_at: str = "document_idle") -> tuple[str, str]:
        """Return combined (js, css) for all scripts matching a URL and run_at timing.

        Returns (combined_js, combined_css) strings.
        """
        all_js = []
        all_css = []

        for ext in self._extensions.values():
            if not ext.enabled:
                continue
            for cs in ext.content_scripts:
                if cs.run_at != run_at:
                    continue
                if not self._url_matches(url, cs.matches):
                    continue
                # Load JS files
                for js_file in cs.js:
                    js_path = ext.path / js_file
                    if js_path.exists():
                        all_js.append(js_path.read_text(encoding="utf-8"))
                # Load CSS files
                for css_file in cs.css:
                    css_path = ext.path / css_file
                    if css_path.exists():
                        all_css.append(css_path.read_text(encoding="utf-8"))

        return "\n".join(all_js), "\n".join(all_css)

    @staticmethod
    def _url_matches(url: str, patterns: list[str]) -> bool:
        """Check if a URL matches any of the match patterns."""
        for pattern in patterns:
            if pattern == "<all_urls>":
                return True
            # Convert match pattern to regex
            # Pattern format: scheme://host/path
            # *:// matches http and https
            regex = pattern
            regex = regex.replace("*://", "(https?|file)://")
            regex = regex.replace("*.", "([a-z0-9.-]*\\.)?")
            regex = regex.replace("/*", "/.*")
            if not regex.endswith(".*"):
                regex += ".*"
            regex = "^" + regex + "$"
            try:
                if re.match(regex, url, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False
