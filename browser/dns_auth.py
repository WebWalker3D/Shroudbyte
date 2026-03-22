"""HMAC-SHA256 signing for authenticated DNS queries between Shroudbyte
and a pfSense DNS server.

Provides request signing/verification and minimal DNS wire-format
query construction and response parsing (RFC 1035).
"""

import hashlib
import hmac
import ipaddress
import os
import struct


def sign_request(shared_secret: bytes, timestamp: str, nonce: str, body: bytes) -> str:
    """Return hex HMAC-SHA256 digest of (timestamp + nonce + body)."""
    message = timestamp.encode() + nonce.encode() + body
    return hmac.new(shared_secret, message, hashlib.sha256).hexdigest()


def verify_request(
    shared_secret: bytes, timestamp: str, nonce: str, body: bytes, signature: str
) -> bool:
    """Verify a request signature using constant-time comparison."""
    expected = sign_request(shared_secret, timestamp, nonce, body)
    return hmac.compare_digest(expected, signature)


def generate_nonce() -> str:
    """Return a random 16-byte hex nonce."""
    return os.urandom(16).hex()


def build_dns_query(domain: str, qtype: int = 1) -> bytes:
    """Build a minimal DNS wire-format query (RFC 1035).

    Args:
        domain: The domain name to query (e.g. "example.com").
        qtype: Query type -- 1 for A, 28 for AAAA.

    Returns:
        Raw bytes of the DNS query packet.
    """
    query_id = struct.unpack("!H", os.urandom(2))[0]

    # Header: ID, flags (RD=1), QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
    flags = 0x0100  # RD bit set
    header = struct.pack("!HHHHHH", query_id, flags, 1, 0, 0, 0)

    # Encode domain name as length-prefixed labels
    qname = b""
    for label in domain.rstrip(".").split("."):
        encoded = label.encode("ascii")
        qname += struct.pack("!B", len(encoded)) + encoded
    qname += b"\x00"  # null terminator

    # QTYPE and QCLASS (IN = 1)
    question = qname + struct.pack("!HH", qtype, 1)

    return header + question


def parse_dns_response(data: bytes) -> tuple[list[str], int]:
    """Parse a DNS wire-format response and extract A/AAAA record addresses.

    Args:
        data: Raw bytes of the DNS response packet.

    Returns:
        Tuple of (list of IP address strings, minimum TTL in seconds).
    """
    if len(data) < 12:
        return [], 0

    # Parse header
    _id, _flags, qdcount, ancount, _nscount, _arcount = struct.unpack(
        "!HHHHHH", data[:12]
    )

    # Sanity-check counts to avoid runaway parsing on malformed packets
    if qdcount > 100 or ancount > 200:
        return [], 0

    offset = 12

    # Skip question section
    for _ in range(qdcount):
        offset = _skip_name(data, offset)
        offset += 4  # QTYPE (2) + QCLASS (2)

    # Parse answer section
    addresses: list[str] = []
    min_ttl = 0xFFFFFFFF
    for _ in range(ancount):
        offset = _skip_name(data, offset)

        if offset + 10 > len(data):
            break

        rtype, _rclass, ttl, rdlength = struct.unpack(
            "!HHIH", data[offset : offset + 10]
        )
        offset += 10

        if offset + rdlength > len(data):
            break

        if rtype == 1 and rdlength == 4:
            # A record
            octets = struct.unpack("!BBBB", data[offset : offset + 4])
            addresses.append("{}.{}.{}.{}".format(*octets))
            min_ttl = min(min_ttl, ttl)
        elif rtype == 28 and rdlength == 16:
            # AAAA record
            addr = ipaddress.IPv6Address(data[offset : offset + 16])
            addresses.append(str(addr))
            min_ttl = min(min_ttl, ttl)

        offset += rdlength

    if not addresses:
        min_ttl = 0

    return addresses, min_ttl


def _skip_name(data: bytes, offset: int) -> int:
    """Advance past a DNS name field, handling compression pointers."""
    while offset < len(data):
        length = data[offset]
        if length == 0:
            # End of name
            return offset + 1
        if (length & 0xC0) == 0xC0:
            # Compressed pointer -- 2 bytes total, done after this
            return offset + 2
        # Regular label
        offset += 1 + length
    return offset
