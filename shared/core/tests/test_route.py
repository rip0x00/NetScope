"""Route packet fixtures and stop-point classification."""

import socket
import struct

import pytest

from netscope_core.routeprobe import (
    Hop,
    build_echo_request,
    checksum,
    classify_route,
    parse_icmp_packet,
)


def ip_packet(source: str, payload: bytes, destination: str = "192.0.2.1") -> bytes:
    header = struct.pack(
        "!BBHHHBBH", 0x45, 0, 20 + len(payload), 0, 0, 64, socket.IPPROTO_ICMP, 0
    )
    return header + socket.inet_aton(source) + socket.inet_aton(destination) + payload


def test_checksum_rfc1071_vector():
    # The worked example from RFC 1071.
    assert checksum(bytes.fromhex("0001f203f4f5f6f7")) == 0x220D


def test_echo_request_checksum_validates():
    packet = build_echo_request(0x1234, 7)
    assert packet[0] == 8  # echo request
    assert checksum(packet) == 0  # a valid checksummed packet sums to zero


def test_parse_echo_reply():
    icmp = struct.pack("!BBHHH", 0, 0, 0, 0x1234, 7) + b"payload"
    message = parse_icmp_packet(ip_packet("93.184.216.34", icmp))
    assert message.type == 0
    assert message.source_ip == "93.184.216.34"
    assert message.identifier == 0x1234
    assert message.sequence == 7


def test_parse_time_exceeded_reads_embedded_probe():
    original_icmp = struct.pack("!BBHHH", 8, 0, 0, 0x1234, 9)
    original_ip = ip_packet("192.0.2.1", original_icmp, destination="93.184.216.34")
    icmp_error = struct.pack("!BBH", 11, 0, 0) + b"\x00\x00\x00\x00" + original_ip
    message = parse_icmp_packet(ip_packet("10.0.0.1", icmp_error))
    assert message.type == 11
    assert message.source_ip == "10.0.0.1"
    assert message.embedded_destination == "93.184.216.34"
    assert message.identifier == 0x1234
    assert message.sequence == 9


def test_parse_rejects_truncated_and_non_icmp():
    with pytest.raises(ValueError):
        parse_icmp_packet(b"\x45\x00\x00")
    not_icmp = struct.pack("!BBHHHBBH", 0x45, 0, 20, 0, 0, 64, 6, 0) + b"\x00" * 8
    with pytest.raises(ValueError):
        parse_icmp_packet(not_icmp)


def hops_with_last(last_ttl):
    return [Hop(ttl=t, ip="10.0.0.1" if t <= last_ttl else None) for t in range(1, last_ttl + 3)]


def test_classify_reached_destination():
    stop, note = classify_route(hops_with_last(6), reached=True, method="icmp")
    assert stop == "destination"


def test_classify_local_stop():
    stop, note = classify_route(hops_with_last(2), reached=False, method="icmp")
    assert stop == "local"
    assert "hop 2" in note


def test_classify_mid_path_stop():
    stop, note = classify_route(hops_with_last(11), reached=False, method="icmp")
    assert stop == "mid-path"


def test_classify_no_response_icmp():
    stop, note = classify_route([Hop(ttl=1), Hop(ttl=2)], reached=False, method="icmp")
    assert stop == "no-response"


def test_classify_no_response_tcp_explains_limitation():
    stop, note = classify_route([Hop(ttl=1)], reached=False, method="tcp")
    assert stop == "no-response"
    assert "raw-socket" in note
