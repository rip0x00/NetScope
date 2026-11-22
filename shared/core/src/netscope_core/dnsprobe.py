"""DNS probing and wire-format DNS.

NetScope looks at DNS from two directions: what the operating system's
resolver returns, and what public resolvers return when asked directly
with hand-built wire-format queries (UDP port 53). Disagreement between
the two views is the signal this module exists to surface.

The wire codec is hand-rolled and handles name compression safely
(pointer loops and truncated packets raise ``ValueError``). Record
types A, AAAA, CNAME, MX, NS, TXT, SOA, PTR, SRV and CAA have proper
rdata parsing; any other type is carried as a hexadecimal string so no
answer is silently dropped.
"""

from __future__ import annotations

import random
import socket
import struct
import time
from dataclasses import dataclass, field

QTYPE_A = 1
QTYPE_NS = 2
QTYPE_CNAME = 5
QTYPE_SOA = 6
QTYPE_PTR = 12
QTYPE_MX = 15
QTYPE_TXT = 16
QTYPE_AAAA = 28
QTYPE_SRV = 33
QTYPE_CAA = 257

TYPE_NAMES = {
    QTYPE_A: "A",
    QTYPE_NS: "NS",
    QTYPE_CNAME: "CNAME",
    QTYPE_SOA: "SOA",
    QTYPE_PTR: "PTR",
    QTYPE_MX: "MX",
    QTYPE_TXT: "TXT",
    QTYPE_AAAA: "AAAA",
    QTYPE_SRV: "SRV",
    QTYPE_CAA: "CAA",
}
NAME_TO_TYPE = {name: number for number, name in TYPE_NAMES.items()}

RCODE_NAMES = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN", 5: "REFUSED"}

DEFAULT_RESOLVERS = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]


# ---------------------------------------------------------------------------
# Wire format
# ---------------------------------------------------------------------------

def _encode_name(name: str) -> bytes:
    out = bytearray()
    for label in name.rstrip(".").split("."):
        encoded = label.encode("utf-8")
        if len(encoded) > 63:
            raise ValueError(f"DNS label too long: {label!r}")
        out.append(len(encoded))
        out.extend(encoded)
    out.append(0)
    return bytes(out)


def build_query(name: str, qtype: int, txid: int | None = None) -> bytes:
    """Build a single-question DNS query packet (recursion desired)."""
    if txid is None:
        txid = random.randrange(0, 65536)
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    return header + _encode_name(name) + struct.pack("!HH", qtype, 1)


def _read_name(data: bytes, offset: int) -> tuple[str, int]:
    """Read a possibly compressed domain name. Returns (name, next offset)."""
    labels: list[str] = []
    jumped = False
    next_offset = offset
    jumps = 0
    while True:
        if offset >= len(data):
            raise ValueError("name runs past end of packet")
        length = data[offset]
        if length == 0:
            if not jumped:
                next_offset = offset + 1
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("truncated compression pointer")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                next_offset = offset + 2
            offset = pointer
            jumped = True
            jumps += 1
            if jumps > 128:
                raise ValueError("compression pointer loop")
            continue
        if length & 0xC0:
            raise ValueError("reserved label bits set")
        start = offset + 1
        end = start + length
        if end > len(data):
            raise ValueError("label runs past end of packet")
        labels.append(data[start:end].decode("utf-8", errors="replace"))
        offset = end
    return ".".join(labels), next_offset


@dataclass
class DNSRecord:
    name: str
    type: str
    value: str
    ttl: int


def _parse_rdata(data: bytes, rtype: int, start: int, rdlen: int) -> str:
    """Decode one record's rdata to its presentation form."""
    end = start + rdlen
    raw = data[start:end]
    if rtype == QTYPE_A and rdlen == 4:
        return socket.inet_ntoa(raw)
    if rtype == QTYPE_AAAA and rdlen == 16:
        return socket.inet_ntop(socket.AF_INET6, raw)
    if rtype in (QTYPE_CNAME, QTYPE_NS, QTYPE_PTR):
        value, _ = _read_name(data, start)
        return value
    if rtype == QTYPE_MX:
        if rdlen < 3:
            raise ValueError("truncated MX rdata")
        (preference,) = struct.unpack("!H", raw[:2])
        exchange, _ = _read_name(data, start + 2)
        return f"{preference} {exchange}"
    if rtype == QTYPE_TXT:
        parts: list[str] = []
        pos = start
        while pos < end:
            size = data[pos]
            pos += 1
            if pos + size > end:
                raise ValueError("truncated TXT string")
            parts.append(data[pos:pos + size].decode("utf-8", errors="replace"))
            pos += size
        return "".join(parts)
    if rtype == QTYPE_SOA:
        mname, pos = _read_name(data, start)
        rname, pos = _read_name(data, pos)
        if pos + 20 > end:
            raise ValueError("truncated SOA rdata")
        serial, refresh, retry, expire, minimum = struct.unpack("!IIIII", data[pos:pos + 20])
        return f"{mname} {rname} {serial} {refresh} {retry} {expire} {minimum}"
    if rtype == QTYPE_SRV:
        if rdlen < 7:
            raise ValueError("truncated SRV rdata")
        priority, weight, port = struct.unpack("!HHH", raw[:6])
        target_name, _ = _read_name(data, start + 6)
        return f"{priority} {weight} {port} {target_name}"
    if rtype == QTYPE_CAA:
        if rdlen < 2:
            raise ValueError("truncated CAA rdata")
        flags = raw[0]
        tag_length = raw[1]
        if 2 + tag_length > rdlen:
            raise ValueError("truncated CAA tag")
        tag = raw[2:2 + tag_length].decode("ascii", errors="replace")
        value = raw[2 + tag_length:].decode("utf-8", errors="replace")
        return f'{flags} {tag} "{value}"'
    return raw.hex()


@dataclass
class DNSMessage:
    txid: int
    rcode: int
    answers: list[DNSRecord] = field(default_factory=list)
    authority: list[DNSRecord] = field(default_factory=list)

    @property
    def rcode_name(self) -> str:
        return RCODE_NAMES.get(self.rcode, f"RCODE{self.rcode}")

    def addresses_for(self, name: str) -> list[str]:
        """A/AAAA values for ``name``, following CNAME chains in the message."""
        result: list[str] = []
        current = name.rstrip(".").lower()
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            next_name: str | None = None
            for record in self.answers:
                if record.name.rstrip(".").lower() != current:
                    continue
                if record.type in ("A", "AAAA"):
                    if record.value not in result:
                        result.append(record.value)
                elif record.type == "CNAME":
                    next_name = record.value.rstrip(".").lower()
            current = next_name or ""
        return result


def _parse_rr_section(data: bytes, offset: int, count: int) -> tuple[list[DNSRecord], int]:
    records: list[DNSRecord] = []
    for _ in range(count):
        name, offset = _read_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("truncated record header")
        rtype, _rclass, ttl, rdlen = struct.unpack("!HHIH", data[offset:offset + 10])
        rdata_start = offset + 10
        rdata_end = rdata_start + rdlen
        if rdata_end > len(data):
            raise ValueError("truncated record data")
        value = _parse_rdata(data, rtype, rdata_start, rdlen)
        type_name = TYPE_NAMES.get(rtype, f"TYPE{rtype}")
        records.append(DNSRecord(name, type_name, value, ttl))
        offset = rdata_end
    return records, offset


def parse_response(data: bytes) -> DNSMessage:
    """Parse a DNS response packet. Raises ValueError on malformed input."""
    if len(data) < 12:
        raise ValueError("packet shorter than DNS header")
    txid, flags, qdcount, ancount, nscount, _ar = struct.unpack("!HHHHHH", data[:12])
    rcode = flags & 0x000F
    offset = 12
    for _ in range(qdcount):
        _name, offset = _read_name(data, offset)
        if offset + 4 > len(data):
            raise ValueError("truncated question section")
        offset += 4
    message = DNSMessage(txid=txid, rcode=rcode)
    message.answers, offset = _parse_rr_section(data, offset, ancount)
    message.authority, offset = _parse_rr_section(data, offset, nscount)
    return message


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------

@dataclass
class ResolverResult:
    resolver: str
    status: str  # ok | nxdomain | servfail | refused | timeout | error
    addresses: list[str] = field(default_factory=list)
    records: list[DNSRecord] = field(default_factory=list)
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class LookupResult:
    """The answer to one application-level record query."""

    name: str
    qtype: str
    resolver: str
    status: str  # ok | nxdomain | servfail | refused | timeout | error
    records: list[DNSRecord] = field(default_factory=list)
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class DNSReport:
    hostname: str
    system_addresses: list[str] = field(default_factory=list)
    system_error: str | None = None
    system_latency_ms: float | None = None
    resolvers: list[ResolverResult] = field(default_factory=list)
    suspect_poisoning: bool = False
    partial_nxdomain: bool = False

    @property
    def resolved_addresses(self) -> list[str]:
        """Best available addresses: system resolver first, then public ones."""
        if self.system_addresses:
            return list(self.system_addresses)
        for result in self.resolvers:
            if result.status == "ok" and result.addresses:
                return list(result.addresses)
        return []


def _query_udp(resolver: str, hostname: str, qtype: int, timeout: float) -> tuple[DNSMessage, float]:
    txid = random.randrange(0, 65536)
    packet = build_query(hostname, qtype, txid)
    family = socket.AF_INET6 if ":" in resolver else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        start = time.perf_counter()
        sock.sendto(packet, (resolver, 53))
        while True:
            data, _addr = sock.recvfrom(4096)
            if len(data) >= 2 and struct.unpack("!H", data[:2])[0] == txid:
                latency = (time.perf_counter() - start) * 1000.0
                return parse_response(data), latency
    finally:
        sock.close()


def _status_for_rcode(rcode: int) -> str:
    return {0: "ok", 2: "servfail", 3: "nxdomain", 5: "refused"}.get(rcode, "error")


def query_resolver(resolver: str, hostname: str, timeout: float = 4.0) -> ResolverResult:
    """Ask one public resolver for a host's addresses over UDP/53."""
    try:
        message, latency = _query_udp(resolver, hostname, QTYPE_A, timeout)
    except (TimeoutError, socket.timeout):
        return ResolverResult(resolver=resolver, status="timeout")
    except (OSError, ValueError) as exc:
        return ResolverResult(resolver=resolver, status="error", error=str(exc))

    result = ResolverResult(resolver=resolver, latency_ms=latency)
    result.status = _status_for_rcode(message.rcode)
    if message.rcode == 0:
        result.records = list(message.answers)
        result.addresses = message.addresses_for(hostname)
        if not result.addresses:
            # No A records (for example a bare CNAME target or an
            # IPv6-only host); try AAAA before giving up.
            try:
                message6, _latency6 = _query_udp(resolver, hostname, QTYPE_AAAA, timeout)
                if message6.rcode == 0:
                    result.records.extend(message6.answers)
                    result.addresses = message6.addresses_for(hostname)
            except (OSError, ValueError):
                pass
    elif message.rcode not in (2, 3, 5):
        result.error = f"unexpected rcode {message.rcode_name}"
    return result


def lookup(
    name: str,
    qtype: str,
    resolver: str = "1.1.1.1",
    timeout: float = 4.0,
) -> LookupResult:
    """Query one record type for ``name`` at an application-level resolver.

    Supports A, AAAA, CNAME, MX, NS, TXT, SOA, PTR, SRV and CAA. The
    system resolver cannot answer arbitrary record types through the
    standard library, so lookups go to the configured resolver over
    UDP/53; the resolver used is recorded in the result.
    """
    qtype = qtype.upper()
    if qtype not in NAME_TO_TYPE:
        raise ValueError(f"unsupported record type: {qtype}")
    result = LookupResult(name=name, qtype=qtype, resolver=resolver, status="error")
    try:
        message, latency = _query_udp(resolver, name, NAME_TO_TYPE[qtype], timeout)
    except (TimeoutError, socket.timeout):
        result.status = "timeout"
        return result
    except (OSError, ValueError) as exc:
        result.error = str(exc)
        return result
    result.latency_ms = latency
    result.status = _status_for_rcode(message.rcode)
    if message.rcode == 0:
        result.records = [r for r in message.answers if r.type == qtype]
    return result


def _system_resolve(hostname: str) -> tuple[list[str], str | None, float]:
    start = time.perf_counter()
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        return [], str(exc), (time.perf_counter() - start) * 1000.0
    latency = (time.perf_counter() - start) * 1000.0
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    return addresses, None, latency


def probe_dns(
    hostname: str,
    resolvers: list[str] | None = None,
    timeout: float = 4.0,
) -> DNSReport:
    """Resolve ``hostname`` via the system resolver and public resolvers."""
    if resolvers is None:
        resolvers = DEFAULT_RESOLVERS
    report = DNSReport(hostname=hostname)
    addresses, error, latency = _system_resolve(hostname)
    report.system_addresses = addresses
    report.system_error = error
    report.system_latency_ms = latency
    report.resolvers = [query_resolver(r, hostname, timeout) for r in resolvers]

    ok_sets = [set(r.addresses) for r in report.resolvers if r.status == "ok" and r.addresses]
    if addresses and ok_sets:
        system_set = set(addresses)
        if all(system_set.isdisjoint(public) for public in ok_sets):
            report.suspect_poisoning = True

    statuses = {r.status for r in report.resolvers}
    if "nxdomain" in statuses and "ok" in statuses:
        report.partial_nxdomain = True
    return report
