"""Tests for browser.passwords — PasswordVault."""

import pytest

from browser import passwords as passwords_mod
from browser.passwords import PasswordVault


MASTER = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _patch_passwords_data_dir(tmp_data_dir, monkeypatch):
    """passwords.py has its own DATA_DIR binding; keep it in sync with storage."""
    monkeypatch.setattr(passwords_mod, "DATA_DIR", tmp_data_dir)


@pytest.fixture
def vault(tmp_data_dir):
    """Return a freshly-setup, unlocked vault."""
    v = PasswordVault()
    v.setup(MASTER)
    return v


# ------------------------------------------------------------------
# Setup / unlock / lock
# ------------------------------------------------------------------

class TestVaultLifecycle:

    def test_setup_creates_vault(self, tmp_data_dir):
        v = PasswordVault()
        assert not v.is_setup()
        v.setup(MASTER)
        assert v.is_setup()
        assert v.is_unlocked

    def test_unlock_correct_password(self, tmp_data_dir):
        v = PasswordVault()
        v.setup(MASTER)
        v.lock()
        assert not v.is_unlocked
        assert v.unlock(MASTER) is True
        assert v.is_unlocked

    def test_unlock_wrong_password(self, tmp_data_dir):
        v = PasswordVault()
        v.setup(MASTER)
        v.lock()
        assert v.unlock("wrong-password") is False
        assert not v.is_unlocked

    def test_lock_clears_entries(self, vault):
        vault.add_entry("https://a.com", "user", "pass")
        assert len(vault.get_all_entries()) == 1
        vault.lock()
        assert vault.get_all_entries() == []
        assert not vault.is_unlocked


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------

class TestVaultCRUD:

    def test_add_entry(self, vault):
        entry = vault.add_entry("https://example.com", "alice", "s3cret")
        assert entry["site_url"] == "https://example.com"
        assert entry["username"] == "alice"
        assert entry["password"] == "s3cret"
        assert "id" in entry
        entries = vault.get_all_entries()
        assert len(entries) == 1

    def test_update_entry(self, vault):
        entry = vault.add_entry("https://example.com", "alice", "old")
        ok = vault.update_entry(entry["id"], password="new")
        assert ok is True
        updated = vault.get_all_entries()[0]
        assert updated["password"] == "new"

    def test_update_nonexistent_entry(self, vault):
        ok = vault.update_entry("no-such-id", password="x")
        assert ok is False

    def test_remove_entry(self, vault):
        entry = vault.add_entry("https://example.com", "alice", "pass")
        assert vault.remove_entry(entry["id"]) is True
        assert vault.get_all_entries() == []

    def test_remove_nonexistent_entry(self, vault):
        assert vault.remove_entry("no-such-id") is False

    def test_crud_when_locked_raises(self, vault):
        vault.lock()
        with pytest.raises(RuntimeError):
            vault.add_entry("https://a.com", "u", "p")
        with pytest.raises(RuntimeError):
            vault.update_entry("id", password="x")
        with pytest.raises(RuntimeError):
            vault.remove_entry("id")


# ------------------------------------------------------------------
# Domain matching
# ------------------------------------------------------------------

class TestGetEntriesForUrl:

    def test_exact_domain_match(self, vault):
        vault.add_entry("https://example.com/login", "u", "p")
        results = vault.get_entries_for_url("https://example.com/other")
        assert len(results) == 1

    def test_www_stripping(self, vault):
        vault.add_entry("https://www.example.com/login", "u", "p")
        results = vault.get_entries_for_url("https://example.com/page")
        assert len(results) == 1

    def test_www_stripping_reverse(self, vault):
        vault.add_entry("https://example.com/login", "u", "p")
        results = vault.get_entries_for_url("https://www.example.com/page")
        assert len(results) == 1

    def test_no_match_different_domain(self, vault):
        vault.add_entry("https://example.com", "u", "p")
        results = vault.get_entries_for_url("https://other.com")
        assert results == []

    def test_multiple_entries_same_domain(self, vault):
        vault.add_entry("https://example.com", "alice", "p1")
        vault.add_entry("https://example.com", "bob", "p2")
        results = vault.get_entries_for_url("https://example.com")
        assert len(results) == 2


# ------------------------------------------------------------------
# Fernet round-trip
# ------------------------------------------------------------------

class TestEncryptionRoundTrip:

    def test_entries_survive_lock_unlock(self, vault):
        """Add entries, lock, unlock with same password, verify entries."""
        vault.add_entry("https://a.com", "user1", "pass1")
        vault.add_entry("https://b.com", "user2", "pass2")
        vault.lock()

        v2 = PasswordVault()
        assert v2.unlock(MASTER) is True
        entries = v2.get_all_entries()
        assert len(entries) == 2
        urls = {e["site_url"] for e in entries}
        assert urls == {"https://a.com", "https://b.com"}

    def test_wrong_password_cannot_read_entries(self, tmp_data_dir):
        v = PasswordVault()
        v.setup(MASTER)
        v.add_entry("https://secret.com", "admin", "hunter2")
        v.lock()

        v2 = PasswordVault()
        assert v2.unlock("wrong") is False
        assert v2.get_all_entries() == []
