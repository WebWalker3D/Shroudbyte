"""Tests for browser.dns_proxy — pure-Python surface only.

The proxy itself runs an asyncio server in a daemon thread and listens
on a real socket, which is too much machinery for unit tests. We cover
the synchronous bits: constructor parsing, update_config, cert
fingerprint comparison, and TLS context selection.
"""

import hashlib
import ssl
from unittest.mock import patch, MagicMock

import pytest

from browser.dns_proxy import ShroudSOCKS5Proxy


SECRET_HEX = "00" * 32  # 32-byte zero secret as hex


@pytest.fixture
def proxy():
    return ShroudSOCKS5Proxy(
        pfsense_url="https://pfsense.test/shroud-dns-query",
        shared_secret=SECRET_HEX,
    )


class TestConstructor:
    def test_secret_decoded_to_bytes(self, proxy):
        assert proxy._shared_secret == b"\x00" * 32

    def test_fingerprint_lowercased_and_stripped(self):
        p = ShroudSOCKS5Proxy(
            "https://x", SECRET_HEX, cert_fingerprint="  AB:CD:Ef  "
        )
        assert p._cert_fingerprint == "ab:cd:ef"

    def test_defaults(self, proxy):
        assert proxy._fallback is True
        assert proxy._dns_cache == {}
        assert proxy._cert_fingerprint == ""


class TestUpdateConfig:
    def test_changes_take_effect_synchronously_when_loop_inactive(self, proxy):
        # No event loop running — _apply runs inline.
        proxy.update_config(
            pfsense_url="https://new.example/q",
            shared_secret="aa" * 32,
            fallback=False,
            cert_fingerprint="DE:AD:BE:EF",
        )
        assert proxy._pfsense_url == "https://new.example/q"
        assert proxy._shared_secret == b"\xaa" * 32
        assert proxy._fallback is False
        assert proxy._cert_fingerprint == "de:ad:be:ef"

    def test_clears_cache_on_credential_change(self, proxy):
        proxy._dns_cache["example.com"] = (["1.2.3.4"], 9999.0)
        proxy.update_config(shared_secret="bb" * 32)
        assert proxy._dns_cache == {}

    def test_partial_update_only_changes_named_fields(self, proxy):
        original_url = proxy._pfsense_url
        proxy.update_config(fallback=False)
        assert proxy._pfsense_url == original_url
        assert proxy._fallback is False


class TestTlsContext:
    def test_default_uses_full_verification(self, proxy):
        ctx = proxy._make_tls_ctx()
        # No fingerprint set — full CA verification.
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_pinned_context_disables_hostname_and_ca(self):
        p = ShroudSOCKS5Proxy("https://x", SECRET_HEX, cert_fingerprint="ab")
        ctx = p._make_tls_ctx()
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE


class TestCertFingerprint:
    def _fake_sock_for(self, der_bytes):
        m = MagicMock(spec=ssl.SSLSocket)
        m.getpeercert.return_value = der_bytes
        return m

    def test_matching_fingerprint_passes(self, proxy):
        der = b"fake-der-bytes"
        proxy._cert_fingerprint = hashlib.sha256(der).hexdigest()
        # Must not raise.
        proxy._verify_cert_fingerprint(self._fake_sock_for(der))

    def test_mismatched_fingerprint_raises(self, proxy):
        proxy._cert_fingerprint = "0" * 64
        with pytest.raises(ssl.SSLError, match="mismatch"):
            proxy._verify_cert_fingerprint(self._fake_sock_for(b"some-der"))

    def test_no_fingerprint_skips_check(self, proxy):
        # Empty fingerprint = legacy mode, accept anything.
        proxy._cert_fingerprint = ""
        sock = self._fake_sock_for(b"whatever")
        proxy._verify_cert_fingerprint(sock)
        # We never call getpeercert when there's nothing to compare.
        sock.getpeercert.assert_not_called()


class TestCacheTtlClamping:
    """The proxy clamps DNS TTLs to [_MIN_TTL, _MAX_TTL] so a
    misconfigured upstream can't pin a long-lived bad answer or
    busy-loop the cache."""

    def test_constants_have_sane_bounds(self):
        from browser.dns_proxy import _MIN_TTL, _MAX_TTL
        assert 0 < _MIN_TTL < _MAX_TTL
