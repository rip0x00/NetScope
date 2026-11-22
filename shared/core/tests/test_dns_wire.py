"""Fixture tests for the DNS wire codec. Packets are built by hand so
the parser is exercised against known bytes, including compression
pointers, with no network involved."""

import socket
import struct

import pytest

from netscope_core.dnsprobe import build_query, parse_response

PTR = b"\xc0\x0c"  # compression pointer to the question name at offset 12


def encode_name(name: str) -> bytes:
    out = bytearray()
    for label in name.rstrip(".").split("."):
        encoded = label.encode()
        out.append(len(encoded))
        out.extend(encoded)
    out.append(0)
    return bytes(out)


def make_packet(answers=(), authority=(), rcode=0, qname="example.com", qtype=1):
    flags = 0x8180 | rcode
    header = struct.pack("!HHHHHH", 0x1234, flags, 1, len(answers), len(authority), 0)
    question = encode_name(qname) + struct.pack("!HH", qtype, 1)
    body = bytearray()
    for name_bytes, rtype, ttl, rdata in list(answers) + list(authority):
        body += name_bytes
        body += struct.pack("!HHIH", rtype, 1, ttl, len(rdata))
        body += rdata
    return header + question + bytes(body)


def test_parse_a_record():
    packet = make_packet(answers=[(PTR, 1, 300, socket.inet_aton("93.184.216.34"))])
    message = parse_response(packet)
    assert message.rcode == 0
    assert len(message.answers) == 1
    record = message.answers[0]
    assert record.type == "A"
    assert record.value == "93.184.216.34"
    assert record.ttl == 300
    assert message.addresses_for("example.com") == ["93.184.216.34"]


def test_parse_aaaa_record():
    address = "2606:2800:220:1:248:1893:25c8:1946"
    packet = make_packet(answers=[(PTR, 28, 300, socket.inet_pton(socket.AF_INET6, address))])
    message = parse_response(packet)
    assert message.answers[0].type == "AAAA"
    assert message.answers[0].value == address


def test_cname_chain_followed():
    packet = make_packet(
        qname="www.example.com",
        answers=[
            (PTR, 5, 300, encode_name("example.com")),
            (encode_name("example.com"), 1, 300, socket.inet_aton("192.0.2.1")),
        ],
    )
    message = parse_response(packet)
    assert message.answers[0].type == "CNAME"
    assert message.addresses_for("www.example.com") == ["192.0.2.1"]


def test_parse_mx_record():
    rdata = struct.pack("!H", 10) + encode_name("mail.example.com")
    packet = make_packet(answers=[(PTR, 15, 3600, rdata)], qtype=15)
    message = parse_response(packet)
    assert message.answers[0].type == "MX"
    assert message.answers[0].value == "10 mail.example.com"


def test_parse_ns_record():
    packet = make_packet(answers=[(PTR, 2, 3600, encode_name("ns1.example.com"))], qtype=2)
    message = parse_response(packet)
    assert message.answers[0].type == "NS"
    assert message.answers[0].value == "ns1.example.com"


def test_parse_txt_record_multiple_strings():
    rdata = bytes([6]) + b"hello " + bytes([5]) + b"world"
    packet = make_packet(answers=[(PTR, 16, 300, rdata)], qtype=16)
    message = parse_response(packet)
    assert message.answers[0].type == "TXT"
    assert message.answers[0].value == "hello world"


def test_parse_soa_in_authority_on_nxdomain():
    rdata = (
        encode_name("ns1.example.com")
        + encode_name("hostmaster.example.com")
        + struct.pack("!IIIII", 2026010101, 7200, 3600, 1209600, 300)
    )
    packet = make_packet(authority=[(PTR, 6, 300, rdata)], rcode=3, qtype=6)
    message = parse_response(packet)
    assert message.rcode_name == "NXDOMAIN"
    assert len(message.authority) == 1
    soa = message.authority[0]
    assert soa.type == "SOA"
    assert soa.value.startswith("ns1.example.com hostmaster.example.com 2026010101")


def test_parse_ptr_record():
    packet = make_packet(
        qname="4.3.2.1.in-addr.arpa",
        answers=[(PTR, 12, 300, encode_name("host.example.com"))],
        qtype=12,
    )
    message = parse_response(packet)
    assert message.answers[0].type == "PTR"
    assert message.answers[0].value == "host.example.com"


def test_parse_srv_record():
    rdata = struct.pack("!HHH", 10, 60, 5060) + encode_name("sip.example.com")
    packet = make_packet(answers=[(PTR, 33, 300, rdata)], qtype=33)
    message = parse_response(packet)
    assert message.answers[0].type == "SRV"
    assert message.answers[0].value == "10 60 5060 sip.example.com"


def test_parse_caa_record():
    rdata = bytes([0, 5]) + b"issue" + b"letsencrypt.org"
    packet = make_packet(answers=[(PTR, 257, 300, rdata)], qtype=257)
    message = parse_response(packet)
    assert message.answers[0].type == "CAA"
    assert message.answers[0].value == '0 issue "letsencrypt.org"'


def test_unknown_type_carried_as_hex():
    packet = make_packet(answers=[(PTR, 99, 300, b"\x01\x02\xab")])
    message = parse_response(packet)
    assert message.answers[0].type == "TYPE99"
    assert message.answers[0].value == "0102ab"


def test_pointer_loop_rejected():
    # Answer name at offset 29 (12 header + 13 question name + 4 qtype/qclass)
    # points at itself.
    question = encode_name("example.com") + struct.pack("!HH", 1, 1)
    answer_offset = 12 + len(question)
    pointer = struct.pack("!H", 0xC000 | answer_offset)
    header = struct.pack("!HHHHHH", 0x1234, 0x8180, 1, 1, 0, 0)
    packet = header + question + pointer + struct.pack("!HHIH", 1, 1, 300, 4) + b"\x01\x02\x03\x04"
    with pytest.raises(ValueError):
        parse_response(packet)


def test_truncated_packet_rejected():
    packet = make_packet(answers=[(PTR, 1, 300, socket.inet_aton("192.0.2.1"))])
    with pytest.raises(ValueError):
        parse_response(packet[:-2])
    with pytest.raises(ValueError):
        parse_response(b"\x00" * 8)


def test_build_query_layout():
    packet = build_query("example.com", 1, txid=0xBEEF)
    txid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", packet[:12])
    assert (txid, qd, an, ns, ar) == (0xBEEF, 1, 0, 0, 0)
    assert flags & 0x0100  # recursion desired
    assert packet[12:] == encode_name("example.com") + struct.pack("!HH", 1, 1)
