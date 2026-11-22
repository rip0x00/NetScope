"""Route probing: where on the path to a host do packets stop?

The layered check in the rest of NetScope looks at the destination.
This module looks at the path: it sends probes with an increasing IP
time-to-live (TTL) so that each router on the path reveals itself by
answering, and records how far the probes get before they stop being
answered.

Two methods are used, in order of preference:

1. ICMP echo requests over a raw socket. Routers answer with ICMP
   Time Exceeded messages that carry their address, and the
   destination answers with an Echo Reply, so every hop's address and
   round-trip time can be recorded. Raw sockets need elevated
   privileges on most systems (root, or CAP_NET_RAW on Linux).
2. TCP connects with the socket's TTL set. No hop addresses can be
   learned this way — the ICMP Time Exceeded messages still arrive,
   but an ordinary socket cannot read them — yet the hop count at
   which the destination starts answering is still measurable, and a
   destination that never answers at any TTL is itself a finding.

The method actually used is recorded in the result; the fallback is
never silent. Packet building and parsing are pure functions so they
can be tested without a network.
"""

from __future__ import annotations

import os
import socket
import struct
import time
from dataclasses import dataclass, field

ICMP_ECHO_REPLY = 0
ICMP_DEST_UNREACHABLE = 3
ICMP_ECHO_REQUEST = 8
ICMP_TIME_EXCEEDED = 11

_PROBE_PAYLOAD = b"netscope route probe"
_MAX_SILENT_HOPS = 5  # stop after this many consecutive unanswered TTLs


# ---------------------------------------------------------------------------
# Packet building and parsing (pure functions)
# ---------------------------------------------------------------------------

def checksum(data: bytes) -> int:
    """The Internet checksum (RFC 1071) of ``data``."""
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def build_echo_request(identifier: int, sequence: int, payload: bytes = _PROBE_PAYLOAD) -> bytes:
    """Build an ICMP Echo Request packet (no IP header)."""
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, 0, identifier, sequence)
    csum = checksum(header + payload)
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, csum, identifier, sequence)
    return header + payload


@dataclass
class ICMPMessage:
    """One parsed ICMP packet, lifted out of its IPv4 envelope."""

    type: int
    code: int
    source_ip: str                       # sender of this packet (a hop, or the destination)
    identifier: int | None = None        # echo id, from this packet or the embedded original
    sequence: int | None = None
    embedded_destination: str | None = None  # destination of the original packet (errors only)


def _parse_ip_header(data: bytes) -> tuple[int, str, str]:
    """Validate an IPv4 header; return (header length, source, destination)."""
    if len(data) < 20:
        raise ValueError("packet shorter than an IPv4 header")
    version = data[0] >> 4
    ihl = (data[0] & 0x0F) * 4
    if version != 4:
        raise ValueError(f"not an IPv4 packet (version {version})")
    if ihl < 20 or ihl > len(data):
        raise ValueError("IPv4 header length out of range")
    if data[9] != socket.IPPROTO_ICMP:
        raise ValueError("IP packet does not carry ICMP")
    source = socket.inet_ntoa(data[12:16])
    destination = socket.inet_ntoa(data[16:20])
    return ihl, source, destination


def parse_icmp_packet(data: bytes) -> ICMPMessage:
    """Parse a full IPv4 packet carrying ICMP. Raises ValueError if malformed.

    For error messages (Time Exceeded, Destination Unreachable) the
    embedded original packet is inspected as well: its destination and
    the echo identifier/sequence it carried identify which probe the
    error belongs to.
    """
    ihl, source, _dest = _parse_ip_header(data)
    icmp = data[ihl:]
    if len(icmp) < 4:
        raise ValueError("truncated ICMP header")
    msg_type, code = icmp[0], icmp[1]
    message = ICMPMessage(type=msg_type, code=code, source_ip=source)
    if msg_type in (ICMP_ECHO_REQUEST, ICMP_ECHO_REPLY):
        if len(icmp) < 8:
            raise ValueError("truncated ICMP echo message")
        message.identifier, message.sequence = struct.unpack("!HH", icmp[4:8])
    elif msg_type in (ICMP_TIME_EXCEEDED, ICMP_DEST_UNREACHABLE):
        if len(icmp) < 8:
            raise ValueError("truncated ICMP error message")
        embedded = icmp[8:]
        eihl, _esrc, edest = _parse_ip_header(embedded)
        message.embedded_destination = edest
        original_icmp = embedded[eihl:]
        if len(original_icmp) >= 8 and original_icmp[0] == ICMP_ECHO_REQUEST:
            message.identifier, message.sequence = struct.unpack("!HH", original_icmp[4:8])
    return message


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class Hop:
    ttl: int
    ip: str | None = None
    rtt_ms: list[float] = field(default_factory=list)
    probes_sent: int = 0

    @property
    def responded(self) -> bool:
        return self.ip is not None

    @property
    def avg_rtt_ms(self) -> float | None:
        if not self.rtt_ms:
            return None
        return sum(self.rtt_ms) / len(self.rtt_ms)


@dataclass
class RouteResult:
    host: str
    destination_ip: str | None
    method: str  # "icmp" | "tcp"
    hops: list[Hop] = field(default_factory=list)
    reached: bool = False
    stop_point: str = "no-response"  # destination | local | mid-path | no-response
    note: str = ""
    error: str | None = None

    @property
    def last_responding_ttl(self) -> int | None:
        ttl = None
        for hop in self.hops:
            if hop.responded:
                ttl = hop.ttl
        return ttl


def classify_route(hops: list[Hop], reached: bool, method: str) -> tuple[str, str]:
    """Classify where a trace stopped. Returns (stop_point, note).

    Pure function of the recorded hops, so the classification can be
    tested without a network.
    """
    last = None
    for hop in hops:
        if hop.responded:
            last = hop.ttl
    if reached:
        where = f"hop {last}" if last is not None else "the destination"
        return "destination", f"The destination answered at {where}; the full path responded."
    if last is None:
        if method == "tcp":
            note = (
                "No probe was answered at any TTL. Hop addresses cannot be read without "
                "raw-socket permission (the TCP fallback was in use), so the trace can only "
                "say that the destination never answered."
            )
        else:
            note = "No hop answered at any TTL; the path is silent from the first router onward."
        return "no-response", note
    if last <= 3:
        note = (
            f"Answers stop at hop {last}, inside or just past the local network. "
            "The problem is likely close to home: the router, the ISP's first hops, "
            "or a local firewall."
        )
        return "local", note
    note = (
        f"Answers stop at hop {last}, partway to the destination. Routers beyond that "
        "point either drop the probes or do not answer them; the break is on the path, "
        "not at the destination."
    )
    if method == "tcp":
        note += (
            " Hop addresses are unknown because ICMP replies cannot be read without "
            "raw-socket permission."
        )
    return "mid-path", note


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------

def _raw_socket_available() -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except OSError:
        return False
    sock.close()
    return True


def _probe_icmp_once(
    destination: str, ttl: int, identifier: int, sequence: int, timeout: float
) -> tuple[str | None, float | None, bool]:
    """Send one echo request with ``ttl``; return (responder, rtt_ms, reached)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        sock.settimeout(timeout)
        packet = build_echo_request(identifier, sequence)
        start = time.perf_counter()
        sock.sendto(packet, (destination, 0))
        deadline = start + timeout
        while time.perf_counter() < deadline:
            try:
                data, _addr = sock.recvfrom(65535)
            except (TimeoutError, socket.timeout, OSError):
                break
            rtt = (time.perf_counter() - start) * 1000.0
            try:
                message = parse_icmp_packet(data)
            except ValueError:
                continue
            if message.identifier is not None and message.identifier != identifier:
                continue
            if message.type == ICMP_TIME_EXCEEDED:
                return message.source_ip, rtt, False
            if message.type == ICMP_ECHO_REPLY:
                return message.source_ip, rtt, True
            if message.type == ICMP_DEST_UNREACHABLE:
                return message.source_ip, rtt, message.source_ip == destination
        return None, None, False
    finally:
        sock.close()


def _trace_icmp(
    destination: str, max_hops: int, probes: int, timeout: float
) -> tuple[list[Hop], bool]:
    identifier = os.getpid() & 0xFFFF
    sequence = 0
    hops: list[Hop] = []
    reached = False
    silent = 0
    for ttl in range(1, max_hops + 1):
        hop = Hop(ttl=ttl)
        for _ in range(probes):
            sequence += 1
            hop.probes_sent += 1
            try:
                responder, rtt, dest = _probe_icmp_once(destination, ttl, identifier, sequence, timeout)
            except OSError:
                responder, rtt, dest = None, None, False
            if responder is not None:
                hop.ip = responder
                if rtt is not None:
                    hop.rtt_ms.append(rtt)
                if dest:
                    reached = True
        hops.append(hop)
        if reached:
            break
        silent = silent + 1 if not hop.responded else 0
        if silent >= _MAX_SILENT_HOPS:
            break
    return hops, reached


def _probe_tcp_once(destination: str, port: int, ttl: int, timeout: float) -> tuple[bool, float | None]:
    """One TCP connect with the socket TTL set; (connected, latency_ms)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        sock.settimeout(timeout)
        start = time.perf_counter()
        sock.connect((destination, port))
        return True, (time.perf_counter() - start) * 1000.0
    except OSError:
        return False, None
    finally:
        sock.close()


def _trace_tcp(
    destination: str, port: int, max_hops: int, timeout: float
) -> tuple[list[Hop], bool]:
    hops: list[Hop] = []
    reached = False
    silent = 0
    for ttl in range(1, max_hops + 1):
        hop = Hop(ttl=ttl, probes_sent=1)
        connected, latency = _probe_tcp_once(destination, port, ttl, timeout)
        if connected:
            hop.ip = destination
            if latency is not None:
                hop.rtt_ms.append(latency)
            reached = True
        hops.append(hop)
        if reached:
            break
        silent += 1
        if silent >= _MAX_SILENT_HOPS:
            break
    return hops, reached


def _resolve_ipv4(host: str) -> str | None:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
    except OSError:
        return None
    return infos[0][4][0] if infos else None


def probe_route(
    host: str,
    max_hops: int = 30,
    probes: int = 3,
    timeout: float = 1.5,
    port: int = 443,
) -> RouteResult:
    """Trace the route to ``host`` as far as probes are answered.

    Uses ICMP echo probes when raw sockets are permitted and falls
    back to TTL-limited TCP connects otherwise. The result records
    which method ran.
    """
    destination = _resolve_ipv4(host)
    if destination is None:
        return RouteResult(
            host=host,
            destination_ip=None,
            method="icmp" if _raw_socket_available() else "tcp",
            error=f"could not resolve {host} to an IPv4 address",
            note=f"NetScope could not resolve {host} to an IPv4 address, so no route could be traced.",
        )
    if _raw_socket_available():
        method = "icmp"
        hops, reached = _trace_icmp(destination, max_hops, probes, timeout)
    else:
        method = "tcp"
        hops, reached = _trace_tcp(destination, port, max_hops, timeout)
    stop_point, note = classify_route(hops, reached, method)
    return RouteResult(
        host=host,
        destination_ip=destination,
        method=method,
        hops=hops,
        reached=reached,
        stop_point=stop_point,
        note=note,
    )
