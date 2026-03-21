#!/usr/bin/env python3
"""
Shroud DNS Server — Authenticated DNS-over-HTTPS relay for pfSense.

Receives HMAC-signed DNS queries over HTTPS from Shroudbyte's SOCKS5
proxy, validates the signature, forwards to local Unbound on 127.0.0.1:53,
and returns the raw DNS response.

Requires only Python stdlib. Designed for FreeBSD / pfSense environments.

Usage:
    # Generate a shared secret:
    python3 -c "import secrets; print(secrets.token_hex(32))" > /usr/local/etc/shroud_dns.key

    # Run the server:
    python3 shroud_dns_server.py \\
        --port 8853 \\
        --cert /usr/local/etc/shroud_dns/cert.pem \\
        --key /usr/local/etc/shroud_dns/key.pem \\
        --secret-file /usr/local/etc/shroud_dns.key

    # Or with all defaults:
    python3 shroud_dns_server.py
"""

import argparse
import hashlib
import hmac
import logging
import socket
import ssl
import struct
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("shroud-dns")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIMESTAMP_WINDOW_SEC = 60
NONCE_EXPIRY_SEC = 120
DNS_UDP_TIMEOUT_SEC = 5
MAX_BODY_BYTES = 4096

# ---------------------------------------------------------------------------
# Nonce tracker (thread-safe)
# ---------------------------------------------------------------------------


class NonceTracker:
    """Tracks seen nonces to prevent replay attacks."""

    def __init__(self, expiry: float = NONCE_EXPIRY_SEC):
        self._lock = threading.Lock()
        self._nonces: dict[str, float] = {}
        self._expiry = expiry
        self._last_cleanup = time.monotonic()

    def check_and_store(self, nonce: str) -> bool:
        """Return True if the nonce is fresh (not seen before). Stores it."""
        now = time.monotonic()
        with self._lock:
            self._maybe_cleanup(now)
            if nonce in self._nonces:
                return False
            self._nonces[nonce] = now
            return True

    def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup < self._expiry:
            return
        cutoff = now - self._expiry
        expired = [k for k, ts in self._nonces.items() if ts < cutoff]
        for k in expired:
            del self._nonces[k]
        if expired:
            log.debug("Cleaned %d expired nonces", len(expired))
        self._last_cleanup = now


# ---------------------------------------------------------------------------
# DNS forwarder
# ---------------------------------------------------------------------------


def forward_dns(query: bytes, unbound_host: str, unbound_port: int) -> bytes:
    """Send a raw DNS query via UDP and return the response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(DNS_UDP_TIMEOUT_SEC)
        sock.sendto(query, (unbound_host, unbound_port))
        data, _ = sock.recvfrom(65535)
        return data
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def make_handler(shared_secret: bytes, nonce_tracker: NonceTracker,
                 unbound_host: str, unbound_port: int):
    """Factory that returns a request handler class with bound config."""

    class ShroudHandler(BaseHTTPRequestHandler):
        # Suppress default stderr logging; we use our own logger.
        def log_message(self, fmt, *args):
            log.info("%s %s", self.client_address[0], fmt % args)

        # ---- Health check ------------------------------------------------

        def do_GET(self):
            if self.path == "/health":
                self._send_text(200, "ok")
                return
            self._send_text(404, "not found")

        # ---- DNS query ---------------------------------------------------

        def do_POST(self):
            if self.path != "/shroud-dns-query":
                self._send_text(404, "not found")
                return

            try:
                # Read body
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length <= 0 or content_length > MAX_BODY_BYTES:
                    self._send_text(403, "forbidden")
                    return
                body = self.rfile.read(content_length)

                # Authenticate
                if not self._authenticate(body):
                    self._send_text(403, "forbidden")
                    return

                # Forward to Unbound
                response = forward_dns(body, unbound_host, unbound_port)
                self._send_bytes(200, "application/dns-message", response)

            except Exception:
                log.exception("Error handling POST from %s",
                              self.client_address[0])
                self._send_text(500, "internal error")

        # ---- Auth helpers ------------------------------------------------

        def _authenticate(self, body: bytes) -> bool:
            ts_str = self.headers.get("X-Shroud-Timestamp", "")
            nonce = self.headers.get("X-Shroud-Nonce", "")
            sig_hex = self.headers.get("X-Shroud-Signature", "")

            if not ts_str or not nonce or not sig_hex:
                log.warning("Missing auth headers from %s",
                            self.client_address[0])
                return False

            # Timestamp window
            try:
                ts_val = int(ts_str)
            except ValueError:
                log.warning("Invalid timestamp from %s",
                            self.client_address[0])
                return False

            now = int(time.time())
            if abs(now - ts_val) > TIMESTAMP_WINDOW_SEC:
                log.warning("Timestamp out of window from %s (delta=%ds)",
                            self.client_address[0], now - ts_val)
                return False

            # Nonce replay
            if not nonce_tracker.check_and_store(nonce):
                log.warning("Replayed nonce from %s", self.client_address[0])
                return False

            # HMAC-SHA256
            ts_bytes = ts_str.encode("ascii")
            nonce_bytes = nonce.encode("ascii")
            sign_message = ts_bytes + nonce_bytes + body

            expected = hmac.new(shared_secret, sign_message,
                                hashlib.sha256).hexdigest()

            if not hmac.compare_digest(expected, sig_hex):
                log.warning("Bad signature from %s", self.client_address[0])
                return False

            return True

        # ---- Response helpers --------------------------------------------

        def _send_text(self, code: int, text: str):
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, code: int, content_type: str, data: bytes):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ShroudHandler


# ---------------------------------------------------------------------------
# CLI & main
# ---------------------------------------------------------------------------


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Shroud DNS — authenticated DoH relay for pfSense")
    p.add_argument("--port", type=int, default=8853,
                   help="HTTPS listen port (default: 8853)")
    p.add_argument("--listen", default="0.0.0.0",
                   help="Bind address (default: 0.0.0.0)")
    p.add_argument("--secret-file",
                   default="/usr/local/etc/shroud_dns.key",
                   help="Path to hex-encoded shared secret")
    p.add_argument("--cert",
                   default="/usr/local/etc/shroud_dns/cert.pem",
                   help="TLS certificate PEM file")
    p.add_argument("--key",
                   default="/usr/local/etc/shroud_dns/key.pem",
                   help="TLS private key PEM file")
    p.add_argument("--unbound", default="127.0.0.1:53",
                   help="Unbound address as host:port (default: 127.0.0.1:53)")
    return p.parse_args(argv)


def load_secret(path: str) -> bytes:
    with open(path, "r") as f:
        hex_str = f.read().strip()
    secret = bytes.fromhex(hex_str)
    if len(secret) < 16:
        raise ValueError("Shared secret must be at least 16 bytes (32 hex chars)")
    return secret


def parse_host_port(addr: str) -> tuple[str, int]:
    host, _, port_str = addr.rpartition(":")
    if not host:
        host = port_str
        port_str = "53"
    return host, int(port_str)


def main() -> None:
    args = parse_args()

    # Load shared secret
    log.info("Loading shared secret from %s", args.secret_file)
    secret = load_secret(args.secret_file)

    # Parse unbound address
    unbound_host, unbound_port = parse_host_port(args.unbound)
    log.info("Forwarding DNS to %s:%d", unbound_host, unbound_port)

    # Build handler
    tracker = NonceTracker()
    handler_cls = make_handler(secret, tracker, unbound_host, unbound_port)

    # Create HTTPS server
    server = HTTPServer((args.listen, args.port), handler_cls)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=args.cert, keyfile=args.key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)

    log.info("Shroud DNS server listening on https://%s:%d", args.listen, args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
