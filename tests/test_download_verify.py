"""Tests for browser.download_verify — hash computation and verification."""

import hashlib
import json

import pytest

from browser.download_verify import (
    compute_hashes,
    save_verification_receipt,
    verify_hash,
)


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"shroudbyte-test-payload\n")
    return f


class TestComputeHashes:
    def test_matches_hashlib(self, sample_file):
        data = sample_file.read_bytes()
        expected = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "sha512": hashlib.sha512(data).hexdigest(),
            "md5":    hashlib.md5(data).hexdigest(),
        }
        assert compute_hashes(sample_file) == expected

    def test_missing_file_returns_empty(self, tmp_path):
        assert compute_hashes(tmp_path / "nope.bin") == {}

    def test_handles_larger_than_chunk(self, tmp_path):
        # The streaming loop uses a 64k chunk; verify > 1 chunk works.
        big = tmp_path / "big.bin"
        big.write_bytes(b"x" * (65536 * 3 + 1))
        h = compute_hashes(big)
        assert h["sha256"] == hashlib.sha256(b"x" * (65536 * 3 + 1)).hexdigest()


class TestVerifyHash:
    def test_correct_sha256_passes(self, sample_file):
        expected = hashlib.sha256(sample_file.read_bytes()).hexdigest()
        r = verify_hash(sample_file, expected)
        assert r.verified is True
        assert r.method == "hash"
        assert r.sha256 == expected

    def test_wrong_sha256_fails(self, sample_file):
        r = verify_hash(sample_file, "0" * 64)
        assert r.verified is False
        assert "mismatch" in r.details

    def test_md5_algorithm(self, sample_file):
        md5 = hashlib.md5(sample_file.read_bytes()).hexdigest()
        assert verify_hash(sample_file, md5, algorithm="md5").verified is True

    def test_unknown_algorithm_falls_back_to_sha256(self, sample_file):
        expected = hashlib.sha256(sample_file.read_bytes()).hexdigest()
        r = verify_hash(sample_file, expected, algorithm="bogus")
        assert r.verified is True

    def test_case_and_whitespace_tolerant(self, sample_file):
        expected = hashlib.sha256(sample_file.read_bytes()).hexdigest()
        # Real-world .sha256 files often have trailing spaces / uppercase.
        assert verify_hash(sample_file, "  " + expected.upper() + "\n").verified is True


class TestSaveReceipt:
    def test_writes_json_receipt(self, sample_file, tmp_path):
        expected = hashlib.sha256(sample_file.read_bytes()).hexdigest()
        result = verify_hash(sample_file, expected)
        receipt_dir = tmp_path / "receipts"
        receipt_path = save_verification_receipt(result, receipt_dir)
        assert receipt_path.exists()
        assert receipt_path.parent == receipt_dir
        assert receipt_path.name.startswith(sample_file.name + ".")
        assert receipt_path.suffix == ".json"
        data = json.loads(receipt_path.read_text())
        assert data["verified"] is True
        assert data["filename"] == sample_file.name
        assert data["sha256"] == expected
