import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def tmp_data_dir(monkeypatch, tmp_path):
    """Redirect all storage I/O to an isolated temp directory."""
    from browser import storage

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    storage._json_cache.clear() if hasattr(storage, "_json_cache") else None
    return tmp_path
