"""Tests for browser.addresses — saved-address CRUD."""

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
