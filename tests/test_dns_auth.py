"""Tests for browser.dns_auth — HMAC signing + DNS wire format."""

import struct

import pytest

from browser import dns_auth


class TestSignAndVerify:
    SECRET = b"shared-secret"
    BODY = b"\x00\x01\x02"

    def test_round_trip(self):
        sig = dns_auth.sign_request(self.SECRET, "1700000000", "nonce", self.BODY)
        assert dns_auth.verify_request(
            self.SECRET, "1700000000", "nonce", self.BODY, sig
        ) is True

    def test_tampered_body_fails(self):
        sig = dns_auth.sign_request(self.SECRET, "ts", "nonce", self.BODY)
        assert dns_auth.verify_request(
            self.SECRET, "ts", "nonce", b"different", sig
        ) is False

    def test_wrong_timestamp_fails(self):
        sig = dns_auth.sign_request(self.SECRET, "100", "nonce", self.BODY)
        assert dns_auth.verify_request(
            self.SECRET, "999", "nonce", self.BODY, sig
        ) is False

    def test_wrong_secret_fails(self):
        sig = dns_auth.sign_request(self.SECRET, "ts", "nonce", self.BODY)
        assert dns_auth.verify_request(
            b"other-secret", "ts", "nonce", self.BODY, sig
        ) is False

    def test_signature_is_hex(self):
        sig = dns_auth.sign_request(self.SECRET, "ts", "nonce", b"")
        # SHA-256 hex digest is 64 chars.
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)


class TestNonce:
    def test_uniqueness(self):
        nonces = {dns_auth.generate_nonce() for _ in range(100)}
        # 16 bytes = 128 bits; 100 random draws should almost never collide.
        assert len(nonces) == 100

    def test_length(self):
        # 16 bytes -> 32 hex characters.
        assert len(dns_auth.generate_nonce()) == 32


class TestBuildDnsQuery:
    def test_header_has_qdcount_one(self):
        q = dns_auth.build_dns_query("example.com")
        _id, flags, qdcount, ancount, _ns, _ar = struct.unpack("!HHHHHH", q[:12])
        assert qdcount == 1
        assert ancount == 0
        # RD (recursion desired) flag should be set.
        assert flags & 0x0100

    def test_qname_label_encoding(self):
        q = dns_auth.build_dns_query("example.com")
        # After 12-byte header: length-prefixed labels for "example" + "com".
        # 7 e x a m p l e 3 c o m 0
        body = q[12:]
        assert body[0] == 7 and body[1:8] == b"example"
        assert body[8] == 3 and body[9:12] == b"com"
        assert body[12] == 0
        qtype, qclass = struct.unpack("!HH", body[13:17])
        assert qtype == 1  # A
        assert qclass == 1  # IN

    def test_aaaa_query_type(self):
        q = dns_auth.build_dns_query("example.com", qtype=28)
        body = q[12:]
        # Skip name (7+1+3+1+0 = 13 bytes for example.com)
        qtype, _ = struct.unpack("!HH", body[13:17])
        assert qtype == 28


class TestParseDnsResponse:
    def _build_response(self, ancount: int, answer_section: bytes) -> bytes:
        """Build a minimal DNS response with 0 questions + given answers."""
        header = struct.pack("!HHHHHH", 0x1234, 0x8180, 0, ancount, 0, 0)
        return header + answer_section

    def test_empty_response(self):
        addrs, ttl = dns_auth.parse_dns_response(b"")
        assert addrs == []
        assert ttl == 0

    def test_truncated_header(self):
        # < 12 bytes — should fail gracefully.
        assert dns_auth.parse_dns_response(b"\x00\x00\x00") == ([], 0)

    def test_single_a_record(self):
        # Compression pointer 0xc00c -> name at offset 12, type=A, class=IN,
        # TTL=300, RDLENGTH=4, RDATA=93.184.216.34
        answer = (
            b"\xc0\x0c"
            + struct.pack("!HHIH", 1, 1, 300, 4)
            + bytes([93, 184, 216, 34])
        )
        resp = self._build_response(1, answer)
        addrs, ttl = dns_auth.parse_dns_response(resp)
        assert addrs == ["93.184.216.34"]
        assert ttl == 300

    def test_min_ttl_returned_across_answers(self):
        a1 = (
            b"\xc0\x0c"
            + struct.pack("!HHIH", 1, 1, 500, 4)
            + bytes([1, 1, 1, 1])
        )
        a2 = (
            b"\xc0\x0c"
            + struct.pack("!HHIH", 1, 1, 60, 4)
            + bytes([2, 2, 2, 2])
        )
        resp = self._build_response(2, a1 + a2)
        addrs, ttl = dns_auth.parse_dns_response(resp)
        assert set(addrs) == {"1.1.1.1", "2.2.2.2"}
        assert ttl == 60

    def test_unknown_record_type_ignored(self):
        # Type 16 (TXT) with weird RDLENGTH — should not appear in output.
        answer = (
            b"\xc0\x0c"
            + struct.pack("!HHIH", 16, 1, 300, 5)
            + b"hello"
        )
        resp = self._build_response(1, answer)
        addrs, _ttl = dns_auth.parse_dns_response(resp)
        assert addrs == []

    def test_runaway_counts_rejected(self):
        # ancount = 5000 should be capped without an infinite loop.
        bogus = struct.pack("!HHHHHH", 0, 0x8180, 0, 5000, 0, 0) + b"x" * 10
        addrs, _ = dns_auth.parse_dns_response(bogus)
        assert addrs == []
