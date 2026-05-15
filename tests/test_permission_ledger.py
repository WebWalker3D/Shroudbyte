"""Tests for browser.permission_ledger — usage log + anomaly detection."""

import csv

from browser import permission_ledger


class TestPermissionLedger:
    def test_log_and_retrieve(self, tmp_data_dir):
        permission_ledger.log_usage("a.com", "geolocation", "granted")
        permission_ledger.log_usage("a.com", "camera",      "denied")
        entries = permission_ledger.get_usage()
        # Most recent first.
        assert len(entries) == 2
        features = [e["feature"] for e in entries]
        assert "geolocation" in features and "camera" in features

    def test_get_usage_filters_by_host(self, tmp_data_dir):
        permission_ledger.log_usage("a.com", "geolocation", "granted")
        permission_ledger.log_usage("b.com", "geolocation", "granted")
        a_entries = permission_ledger.get_usage(host="a.com")
        assert all(e["host"] == "a.com" for e in a_entries)
        assert len(a_entries) == 1

    def test_get_usage_limit(self, tmp_data_dir):
        for i in range(20):
            permission_ledger.log_usage("a.com", "feature", "granted")
        assert len(permission_ledger.get_usage(limit=5)) == 5

    def test_anomaly_detection(self, tmp_data_dir):
        # 12 quick events from one host should trigger the threshold=10 rule.
        for _ in range(12):
            permission_ledger.log_usage("noisy.com", "clipboard-read", "granted")
        # One quiet host that should NOT show up.
        permission_ledger.log_usage("quiet.com", "clipboard-read", "granted")

        anomalies = permission_ledger.get_anomalies(threshold=10, hours=1)
        anomalous_hosts = {a["host"] for a in anomalies}
        assert "noisy.com" in anomalous_hosts
        assert "quiet.com" not in anomalous_hosts

    def test_export_writes_csv(self, tmp_data_dir, tmp_path):
        permission_ledger.log_usage("a.com", "geolocation", "granted")
        permission_ledger.log_usage("a.com", "camera",      "denied")
        out = tmp_path / "perms.csv"
        permission_ledger.export_log(str(out))
        assert out.exists()
        rows = list(csv.reader(out.open()))
        # Header + 2 entries.
        assert len(rows) >= 3
        # Both features present in the body.
        body = "\n".join(",".join(r) for r in rows[1:])
        assert "geolocation" in body and "camera" in body
