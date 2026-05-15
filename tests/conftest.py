import os
import tempfile

import pytest

# QtWebEngineWidgets refuses to import after a QCoreApplication exists
# unless this flag is set first. pytest-qt creates a QApplication during
# session setup, so test modules that drag in browser.webview transitively
# (browser.mixins.tabs, browser.mainwindow) need the flag set BEFORE that
# happens — i.e. before any other test imports.
try:
    from PyQt6.QtCore import Qt, QCoreApplication
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
except Exception:
    pass


@pytest.fixture(autouse=True)
def tmp_data_dir(monkeypatch, tmp_path):
    """Redirect all storage I/O to an isolated temp directory."""
    from browser import storage

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    storage._json_cache.clear() if hasattr(storage, "_json_cache") else None
    return tmp_path
