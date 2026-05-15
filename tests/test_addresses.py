"""Tests for browser.addresses — saved-address CRUD."""

import pytest

from browser import addresses


VALID_FIELDS = {
    "name": "Ada Lovelace",
    "street-address": "1 Foo St",
    "address-level2": "Springfield",
    "postal-code": "12345",
    "country": "US",
    "email": "ada@example.com",
}


class TestAddRemove:
    def test_add_creates_entry_with_id_and_timestamps(self, tmp_data_dir):
        a = addresses.add_address("Home", VALID_FIELDS)
        assert a.id and len(a.id) >= 8
        assert a.label == "Home"
        assert a.created_at > 0
        assert a.updated_at == a.created_at

    def test_blank_label_falls_back(self, tmp_data_dir):
        a = addresses.add_address("", VALID_FIELDS)
        assert a.label == "Untitled"

    def test_remove(self, tmp_data_dir):
        a = addresses.add_address("Home", VALID_FIELDS)
        assert addresses.remove_address(a.id) is True
        assert addresses.get_address(a.id) is None

    def test_remove_missing_returns_false(self, tmp_data_dir):
        assert addresses.remove_address("does-not-exist") is False


class TestFieldSanitization:
    def test_unknown_keys_dropped(self, tmp_data_dir):
        a = addresses.add_address("Home", {
            "name": "Ada",
            "moon_phase": "waxing",      # not a real autocomplete token
            "credit-card-number": "BAD", # not in our allowlist (intentional)
        })
        assert "name" in a.fields
        assert "moon_phase" not in a.fields
        assert "credit-card-number" not in a.fields

    def test_empty_and_none_values_dropped(self, tmp_data_dir):
        a = addresses.add_address("Home", {
            "name": "Ada",
            "given-name": "",
            "family-name": None,
            "email": "   ",  # whitespace only
        })
        assert list(a.fields.keys()) == ["name"]

    def test_values_coerced_to_string_and_trimmed(self, tmp_data_dir):
        a = addresses.add_address("Home", {
            "postal-code": 12345,
            "name": "  Padded  ",
        })
        assert a.fields["postal-code"] == "12345"
        assert a.fields["name"] == "Padded"


class TestListing:
    def test_sorted_most_recently_updated_first(self, tmp_data_dir, monkeypatch):
        import time
        counter = iter(range(1000, 2000))
        monkeypatch.setattr(time, "time", lambda: float(next(counter)))
        a = addresses.add_address("Old", VALID_FIELDS)
        b = addresses.add_address("New", VALID_FIELDS)
        listed = addresses.list_addresses()
        assert [x.id for x in listed] == [b.id, a.id]

    def test_update_bumps_updated_at(self, tmp_data_dir, monkeypatch):
        import time
        counter = iter(range(1000, 2000))
        monkeypatch.setattr(time, "time", lambda: float(next(counter)))
        a = addresses.add_address("Old", VALID_FIELDS)
        b = addresses.add_address("New", VALID_FIELDS)
        addresses.update_address(a.id, label="Older but freshly edited")
        listed = addresses.list_addresses()
        # `a` was touched last, so it moves to the front.
        assert listed[0].id == a.id
        assert listed[0].label == "Older but freshly edited"


class TestUpdate:
    def test_partial_update_keeps_other_fields(self, tmp_data_dir):
        a = addresses.add_address("Home", VALID_FIELDS)
        addresses.update_address(a.id, label="Renamed")
        got = addresses.get_address(a.id)
        assert got.label == "Renamed"
        assert got.fields["street-address"] == "1 Foo St"

    def test_update_unknown_returns_false(self, tmp_data_dir):
        assert addresses.update_address("nope", label="x") is False


import os

from browser import crypto


class TestEncryption:
    """addresses.dat is plain JSON when no key is set; AES-GCM encrypted when one is."""

    @pytest.fixture(autouse=True)
    def reset_key(self):
        addresses.set_encryption_key(None)
        yield
        addresses.set_encryption_key(None)

    def test_plain_json_when_no_key(self, tmp_data_dir):
        a = addresses.add_address("Home", VALID_FIELDS)
        blob = (tmp_data_dir / "addresses.dat").read_bytes()
        # First byte tells us it's a JSON array, not the version byte 0x02.
        assert blob[:1] == b"["
        assert blob[0] != crypto.VAULT_VERSION
        assert a.id.encode() in blob

    def test_encrypted_when_key_set(self, tmp_data_dir):
        key = os.urandom(32)
        addresses.set_encryption_key(key)
        a = addresses.add_address("Home", VALID_FIELDS)
        blob = (tmp_data_dir / "addresses.dat").read_bytes()
        # First byte is the AES-GCM version sentinel.
        assert blob[0] == crypto.VAULT_VERSION
        # Plaintext should be unrecoverable from the on-disk bytes.
        assert a.id.encode() not in blob
        # But the round-trip with the same key still works.
        assert addresses.get_address(a.id) is not None

    def test_locking_hides_entries(self, tmp_data_dir):
        key = os.urandom(32)
        addresses.set_encryption_key(key)
        a = addresses.add_address("Home", VALID_FIELDS)
        # "Lock" the vault — clear the module key.
        addresses.set_encryption_key(None)
        # Encrypted file with no key returns empty rather than raising.
        assert addresses.list_addresses() == []
        # Re-unlocking restores access.
        addresses.set_encryption_key(key)
        assert any(x.id == a.id for x in addresses.list_addresses())

    def test_wrong_key_quarantines_file(self, tmp_data_dir):
        key = os.urandom(32)
        addresses.set_encryption_key(key)
        addresses.add_address("Home", VALID_FIELDS)
        # Switch to a bogus key — load should fail and rename the file
        # aside rather than silently letting the next save clobber it.
        addresses.set_encryption_key(os.urandom(32))
        assert addresses.list_addresses() == []
        assert not (tmp_data_dir / "addresses.dat").exists()
        assert list(tmp_data_dir.glob("addresses.dat.corrupted-*"))

    def test_legacy_json_migrated_on_first_read(self, tmp_data_dir):
        # Simulate an MVP-era addresses.json sitting in the data dir.
        import json as _json
        legacy = tmp_data_dir / "addresses.json"
        entries = [{
            "id": "legacy-id",
            "label": "OldHome",
            "fields": {"name": "Ada"},
            "created_at": 1.0,
            "updated_at": 1.0,
        }]
        legacy.write_text(_json.dumps(entries))

        addrs = addresses.list_addresses()
        assert any(a.label == "OldHome" for a in addrs)
        # The legacy file is consumed.
        assert not legacy.exists()
        # And the new container is in place.
        assert (tmp_data_dir / "addresses.dat").exists()

    def test_round_trip_after_format_switch(self, tmp_data_dir):
        # Plain → encrypted: a save under a new key should re-encrypt.
        a = addresses.add_address("Home", VALID_FIELDS)
        key = os.urandom(32)
        addresses.set_encryption_key(key)
        # The on-disk file was plain JSON; add another address (which
        # triggers a save) and confirm both addresses survive AND the
        # file is now encrypted.
        b = addresses.add_address("Work", VALID_FIELDS)
        blob = (tmp_data_dir / "addresses.dat").read_bytes()
        assert blob[0] == crypto.VAULT_VERSION
        ids = {x.id for x in addresses.list_addresses()}
        assert {a.id, b.id} == ids
