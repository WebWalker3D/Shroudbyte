"""Tests for browser.profiles — profile CRUD and URL→profile matching.

QWebEngineProfile creation needs a live QApplication, so we exercise
only the pure-Python state management surface here: load/save, add,
remove, update, and match_profile_for_url.
"""

import pytest

from browser import storage
from browser.profiles import ProfileManager, _DEFAULT_PROFILES


class TestLoading:
    def test_seeds_default_profiles_on_first_run(self, tmp_data_dir):
        m = ProfileManager()
        names = [p.name for p in m.list_profiles()]
        assert set(names) == {p["name"] for p in _DEFAULT_PROFILES}
        # And persists them so the second load doesn't re-seed.
        assert (tmp_data_dir / "profiles.json").exists()

    def test_loads_existing(self, tmp_data_dir):
        storage._save_json("profiles.json", [
            {"name": "Default", "color": "#000", "auto_assign": []},
            {"name": "Custom",  "color": "#fff", "auto_assign": ["example.com"]},
        ])
        m = ProfileManager()
        names = sorted(p.name for p in m.list_profiles())
        assert names == ["Custom", "Default"]
        custom = m.get_profile("Custom")
        assert custom.color == "#fff"
        assert custom.auto_assign == ["example.com"]


class TestAddRemove:
    def test_add_persists_and_returns_true(self, tmp_data_dir):
        m = ProfileManager()
        assert m.add_profile("Research", color="#abc") is True
        assert m.get_profile("Research").color == "#abc"
        m2 = ProfileManager()
        assert m2.get_profile("Research") is not None

    def test_add_duplicate_returns_false(self, tmp_data_dir):
        m = ProfileManager()
        m.add_profile("Dup")
        assert m.add_profile("Dup") is False

    def test_remove_persists(self, tmp_data_dir):
        m = ProfileManager()
        m.add_profile("Temp")
        assert m.remove_profile("Temp") is True
        m2 = ProfileManager()
        assert m2.get_profile("Temp") is None

    def test_cannot_remove_default(self, tmp_data_dir):
        m = ProfileManager()
        assert m.remove_profile("Default") is False
        assert m.get_profile("Default") is not None


class TestUpdate:
    def test_update_color_and_auto_assign(self, tmp_data_dir):
        m = ProfileManager()
        m.add_profile("Corp")
        m.update_profile("Corp", color="#abcdef", auto_assign=["intra.net"])
        m2 = ProfileManager()
        w = m2.get_profile("Corp")
        assert w.color == "#abcdef"
        assert w.auto_assign == ["intra.net"]

    def test_update_unknown_is_safe(self, tmp_data_dir):
        m = ProfileManager()
        # Should not raise.
        m.update_profile("Nope", color="#000")


class TestUrlMatching:
    def test_default_when_no_rule_matches(self, tmp_data_dir):
        m = ProfileManager()
        assert m.match_profile_for_url("https://nobody.example/") == "Default"

    def test_exact_host_match(self, tmp_data_dir):
        m = ProfileManager()
        m.add_profile("Corp", auto_assign=["company.com"])
        assert m.match_profile_for_url("https://company.com/page") == "Corp"

    def test_subdomain_match(self, tmp_data_dir):
        m = ProfileManager()
        m.add_profile("Corp", auto_assign=["company.com"])
        assert m.match_profile_for_url("https://mail.company.com/x") == "Corp"

    def test_non_subdomain_doesnt_match(self, tmp_data_dir):
        m = ProfileManager()
        m.add_profile("Corp", auto_assign=["company.com"])
        # Partial-suffix match must not fire: notcompany.com != company.com.
        assert m.match_profile_for_url("https://notcompany.com/") == "Default"
