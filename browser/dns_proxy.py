"""SOCKS5 proxy server with authenticated DNS resolution via pfSense DoH.

Runs as a daemon thread inside the Shroudbyte process, listening on
127.0.0.1 with an OS-assigned port.  When a SOCKS5 CONNECT targets a
domain name (ATYP 0x03), the domain is resolved through an
HMAC-authenticated DNS-over-HTTPS query to a pfSense server.  All other
address types (IPv4, IPv6) are connected directly.

Protocol: RFC 1928 (SOCKS5), no-auth method only.
DNS transport: application/dns-message over HTTPS (RFC 8484 style).
"""

import asyncio
import hashlib
import http.client
import logging
import socket
import ssl
import struct
import threading
import time
import urllib.parse
import urllib.request
from functools import partial
from typing import Optional

from .dns_auth import build_dns_query, generate_nonce, parse_dns_response, sign_request

logger = logging.getLogger(__name__)

# SOCKS5 constants
SOCKS_VERSION = 0x05
AUTH_NONE = 0x00
CMD_CONNECT = 0x01
ATYP_IPV4 = 0x01
ATYP_DOMAIN = 0x03
ATYP_IPV6 = 0x04

# SOCKS5 reply codes
REP_SUCCESS = 0x00
REP_GENERAL_FAILURE = 0x01
REP_HOST_UNREACHABLE = 0x04
REP_CONNECTION_REFUSED = 0x05

# DNS cache TTL bounds (seconds)
_MIN_TTL = 30
_MAX_TTL = 300

# Relay buffer size
_BUF_SIZE = 8192


class ShroudSOCKS5Proxy:
    """SOCKS5 proxy with authenticated DoH resolution against pfSense."""

    def __init__(
        self,
        pfsense_url: str,
        shared_secret: str,
        fallback: bool = True,
        cert_fingerprint: str = "",
    ) -> None:
        """
        Args:
            pfsense_url: Full DoH endpoint URL including path, e.g.
                ``"https://pfsense.local:8853/shroud-dns-query"``.
                (Callers pass the base URL from settings with path appended.)
            shared_secret: Hex-encoded HMAC-SHA256 shared secret.
            fallback: If *True*, fall back to system DNS when pfSense is
                unreachable.
            cert_fingerprint: Expected SHA-256 fingerprint of the server's
                TLS certificate (hex).  When set, the proxy pins the cert
                and rejects connections whose fingerprint doesn't match.
                When empty, verification is skipped (legacy behaviour).
        """
        self._pfsense_url = pfsense_url
        self._shared_secret = bytes.fromhex(shared_secret)
        self._fallback = fallback
        self._cert_fingerprint = cert_fingerprint.lower().strip()

        self._dns_cache: dict[str, tuple[list[str], float]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[asyncio.AbstractServer] = None
        self._port: int = 0
        self._started = threading.Event()

    # ------------------------------------------------------------------
    # TLS certificate pinning
    # ------------------------------------------------------------------

    @staticmethod
    def _make_noverify_ctx() -> ssl.SSLContext:
        """Create a TLS context that skips certificate verification."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _verify_cert_fingerprint(self, sock: ssl.SSLSocket) -> None:
        """Check the peer cert fingerprint on an already-connected TLS socket.

        Raises ``ssl.SSLError`` if a fingerprint is configured and the
        peer cert doesn't match.
        """
        if not self._cert_fingerprint:
            return
        der = sock.getpeercert(binary_form=True)
        actual = hashlib.sha256(der).hexdigest()
        if actual != self._cert_fingerprint:
            raise ssl.SSLError(
                f"Certificate fingerprint mismatch: "
                f"expected {self._cert_fingerprint}, got {actual}"
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> int:
        """Start the proxy in a daemon thread.

        Returns:
            The local port number the proxy is listening on.
        """
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._started.wait()
        return self._port

    def stop(self) -> None:
        """Shut down the proxy gracefully."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def update_config(
        self,
        pfsense_url: str = None,
        shared_secret: str = None,
        fallback: bool = None,
        cert_fingerprint: str = None,
    ) -> None:
        """Update configuration at runtime (e.g. from a settings dialog).

        Thread-safe: mutations are scheduled on the event-loop thread.
        """

        def _apply() -> None:
            if pfsense_url is not None:
                self._pfsense_url = pfsense_url
            if shared_secret is not None:
                self._shared_secret = bytes.fromhex(shared_secret)
            if fallback is not None:
                self._fallback = fallback
            if cert_fingerprint is not None:
                self._cert_fingerprint = cert_fingerprint.lower().strip()
            # Flush the cache when credentials change.
            self._dns_cache.clear()

        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(_apply)
        else:
            _apply()

    @property
    def port(self) -> int:
        """The port the proxy is listening on."""
        return self._port

    # ------------------------------------------------------------------
    # Event-loop entry point (runs in daemon thread)
    # ------------------------------------------------------------------

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_server())
            self._started.set()
            self._loop.run_forever()
        finally:
            if self._server is not None:
                self._server.close()
                self._loop.run_until_complete(self._server.wait_closed())
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    async def _start_server(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, "127.0.0.1", 0
        )
        addr = self._server.sockets[0].getsockname()
        self._port = addr[1]
        logger.info("SOCKS5 proxy listening on 127.0.0.1:%d", self._port)

    # ------------------------------------------------------------------
    # SOCKS5 session handler
    # ------------------------------------------------------------------

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        remote_writer: Optional[asyncio.StreamWriter] = None
        try:
            # --- Greeting ---
            header = await reader.readexactly(2)
            version, nmethods = struct.unpack("!BB", header)
            if version != SOCKS_VERSION:
                return
            methods = await reader.readexactly(nmethods)
            if AUTH_NONE not in methods:
                writer.write(struct.pack("!BB", SOCKS_VERSION, 0xFF))
                await writer.drain()
                return
            writer.write(struct.pack("!BB", SOCKS_VERSION, AUTH_NONE))
            await writer.drain()

            # --- Request ---
            req_header = await reader.readexactly(4)
            ver, cmd, _rsv, atyp = struct.unpack("!BBBB", req_header)
            if ver != SOCKS_VERSION or cmd != CMD_CONNECT:
                await self._send_reply(writer, REP_GENERAL_FAILURE, atyp)
                return

            # Read destination address
            if atyp == ATYP_IPV4:
                raw = await reader.readexactly(4)
                dst_addr = socket.inet_ntoa(raw)
            elif atyp == ATYP_DOMAIN:
                length = (await reader.readexactly(1))[0]
                dst_addr = (await reader.readexactly(length)).decode("ascii")
            elif atyp == ATYP_IPV6:
                raw = await reader.readexactly(16)
                dst_addr = socket.inet_ntop(socket.AF_INET6, raw)
            else:
                await self._send_reply(writer, REP_GENERAL_FAILURE, ATYP_IPV4)
                return

            dst_port = struct.unpack("!H", await reader.readexactly(2))[0]

            # --- Resolve domain if needed ---
            connect_addr = dst_addr
            if atyp == ATYP_DOMAIN:
                try:
                    ips = await self._resolve(dst_addr)
                    if not ips:
                        raise OSError("no addresses returned")
                    connect_addr = ips[0]
                except Exception:
                    logger.error("DNS resolution failed for %s", dst_addr)
                    await self._send_reply(writer, REP_HOST_UNREACHABLE, ATYP_IPV4)
                    return

            # --- Connect to remote ---
            try:
                remote_reader, remote_writer = await asyncio.open_connection(
                    connect_addr, dst_port
                )
            except ConnectionRefusedError:
                logger.debug("Connection refused: %s:%d", connect_addr, dst_port)
                await self._send_reply(writer, REP_CONNECTION_REFUSED, ATYP_IPV4)
                return
            except OSError:
                logger.debug("Connection failed: %s:%d", connect_addr, dst_port)
                await self._send_reply(writer, REP_HOST_UNREACHABLE, ATYP_IPV4)
                return

            # --- Success reply ---
            await self._send_reply(writer, REP_SUCCESS, ATYP_IPV4)

            # --- Relay ---
            await self._relay(reader, writer, remote_reader, remote_writer)

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            logger.exception("Unhandled error in SOCKS5 session")
        finally:
            writer.close()
            if remote_writer is not None:
                remote_writer.close()

    # ------------------------------------------------------------------
    # SOCKS5 helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_reply(
        writer: asyncio.StreamWriter, rep: int, atyp: int
    ) -> None:
        """Send a SOCKS5 reply with a zeroed bind address."""
        # VER  REP  RSV  ATYP  BND.ADDR(IPv4 0.0.0.0)  BND.PORT(0)
        writer.write(
            struct.pack("!BBBB", SOCKS_VERSION, rep, 0x00, ATYP_IPV4)
            + b"\x00\x00\x00\x00"
            + struct.pack("!H", 0)
        )
        await writer.drain()

    # ------------------------------------------------------------------
    # Bidirectional relay
    # ------------------------------------------------------------------

    @staticmethod
    async def _relay(
        c_reader: asyncio.StreamReader,
        c_writer: asyncio.StreamWriter,
        r_reader: asyncio.StreamReader,
        r_writer: asyncio.StreamWriter,
    ) -> None:
        async def _pipe(
            src: asyncio.StreamReader, dst: asyncio.StreamWriter
        ) -> None:
            try:
                while True:
                    data = await src.read(_BUF_SIZE)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            except (ConnectionResetError, BrokenPipeError, OSError):
                pass
            finally:
                try:
                    dst.close()
                except OSError:
                    pass

        await asyncio.gather(
            _pipe(c_reader, r_writer),
            _pipe(r_reader, c_writer),
            return_exceptions=True,
        )

    # ------------------------------------------------------------------
    # DNS resolution (authenticated DoH with cache)
    # ------------------------------------------------------------------

    async def _resolve(self, domain: str) -> list[str]:
        """Resolve *domain* via authenticated DoH, with cache and fallback."""
        now = time.monotonic()

        # Check cache
        cached = self._dns_cache.get(domain)
        if cached is not None:
            ips, expires = cached
            if now < expires:
                return ips

        # Try pfSense DoH
        try:
            ips = await self._resolve_doh(domain)
            ttl = max(_MIN_TTL, min(_MAX_TTL, _MAX_TTL))
            self._dns_cache[domain] = (ips, now + ttl)
            return ips
        except Exception:
            logger.warning(
                "DoH resolution failed for %s, fallback=%s", domain, self._fallback
            )
            if not self._fallback:
                raise

        # Fallback to system DNS
        return await self._resolve_system(domain)

    async def _resolve_doh(self, domain: str) -> list[str]:
        """Query pfSense DoH endpoint for *domain*."""
        wire_query = build_dns_query(domain, qtype=1)  # A record

        timestamp = str(int(time.time()))
        nonce = generate_nonce()
        signature = sign_request(self._shared_secret, timestamp, nonce, wire_query)

        headers = {
            "Content-Type": "application/dns-message",
            "Accept": "application/dns-message",
            "X-Shroud-Timestamp": timestamp,
            "X-Shroud-Nonce": nonce,
            "X-Shroud-Signature": signature,
        }

        loop = asyncio.get_running_loop()
        response_data: bytes = await loop.run_in_executor(
            None, partial(self._do_https_request, wire_query, headers)
        )

        ips = parse_dns_response(response_data)
        if not ips:
            raise OSError("DoH returned no addresses for " + domain)
        return ips

    def _do_https_request(self, body: bytes, headers: dict) -> bytes:
        """Perform a blocking HTTPS POST with cert-fingerprint pinning.

        Uses ``http.client.HTTPSConnection`` so the fingerprint can be
        verified on the *same* TLS socket before any application data is
        sent — no TOCTOU gap.
        """
        parsed = urllib.parse.urlparse(self._pfsense_url)
        conn = http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            context=self._make_noverify_ctx(),
            timeout=5,
        )
        try:
            conn.connect()
            self._verify_cert_fingerprint(conn.sock)
            conn.request("POST", parsed.path, body=body, headers=headers)
            resp = conn.getresponse()
            return resp.read()
        finally:
            conn.close()

    @staticmethod
    async def _resolve_system(domain: str) -> list[str]:
        """Resolve *domain* using the system resolver as a fallback."""
        loop = asyncio.get_running_loop()
        infos = await loop.run_in_executor(
            None,
            partial(
                socket.getaddrinfo,
                domain,
                None,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM,
            ),
        )
        seen: set[str] = set()
        ips: list[str] = []
        for family, _type, _proto, _canon, sockaddr in infos:
            addr = sockaddr[0]
            if addr not in seen:
                seen.add(addr)
                ips.append(addr)
        return ips
