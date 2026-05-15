"""Tests for browser.keyring_backend — graceful-degradation behavior."""

import pytest

from browser import keyring_backend


@pytest.fixture(autouse=True)
def reset_cache():
    """is_available() caches its first result; clear between tests."""
    keyring_backend._available = None
    yield
    keyring_backend._available = None


class TestUnavailableBackend:
    """When the keyring package is missing or the backend doesn't work,
    every public function should return None/False without raising."""

    def test_get_store_delete_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(keyring_backend, "_IMPORT_OK", False)
        assert keyring_backend.is_available() is False
        assert keyring_backend.store_secret("k", "v") is False
        assert keyring_backend.get_secret("k") is None
        assert keyring_backend.delete_secret("k") is False

    def test_caches_first_probe(self, monkeypatch):
        monkeypatch.setattr(keyring_backend, "_IMPORT_OK", False)
        keyring_backend.is_available()
        # Flip the underlying state — cache should win.
        monkeypatch.setattr(keyring_backend, "_IMPORT_OK", True)
        assert keyring_backend.is_available() is False


class TestWithFakeKeyring:
    """Inject a fake keyring backend to exercise the happy paths."""

    @pytest.fixture
    def fake_kr(self, monkeypatch):
        store: dict[tuple, str] = {}

        class FakeBackend:
            pass

        class FakeKeyring:
            errors = type("errors", (), {})

            def get_keyring(self):
                return FakeBackend()

            def set_password(self, service, key, value):
                store[(service, key)] = value

            def get_password(self, service, key):
                return store.get((service, key))

            def delete_password(self, service, key):
                store.pop((service, key), None)

        fake = FakeKeyring()
        monkeypatch.setattr(keyring_backend, "_keyring", fake)
        monkeypatch.setattr(keyring_backend, "_IMPORT_OK", True)
        return fake, store

    def test_store_get_delete_round_trip(self, fake_kr):
        _kr, store = fake_kr
        assert keyring_backend.store_secret("foo", "bar") is True
        assert keyring_backend.get_secret("foo") == "bar"
        assert keyring_backend.delete_secret("foo") is True
        assert keyring_backend.get_secret("foo") is None

    def test_get_missing_returns_none(self, fake_kr):
        assert keyring_backend.is_available() is True
        assert keyring_backend.get_secret("never-set") is None

    def test_service_name_is_isolated(self, fake_kr):
        _kr, store = fake_kr
        keyring_backend.store_secret("k", "v")
        # Anything stored uses SERVICE_NAME, not a per-test prefix.
        assert (keyring_backend.SERVICE_NAME, "k") in store


class TestInsecureBackendRejected:
    def test_plaintext_backend_treated_as_unavailable(self, monkeypatch):
        class PlaintextBackend:  # name contains "plaintext"
            pass

        class FakeKeyring:
            errors = type("errors", (), {})

            def get_keyring(self):
                return PlaintextBackend()

        monkeypatch.setattr(keyring_backend, "_keyring", FakeKeyring())
        monkeypatch.setattr(keyring_backend, "_IMPORT_OK", True)
        assert keyring_backend.is_available() is False
