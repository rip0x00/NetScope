"""Local network interface inventory, standard library only.

The standard library has no per-interface address API, so this module
returns what is knowable portably and records the rest as explicit
limitations instead of inventing data:

- Interface names and indices come from ``socket.if_nameindex()``
  where the platform provides it (POSIX systems and Windows).
- The machine's own addresses come from resolving the local hostname.
- The primary outbound IPv4 address comes from the address the kernel
  selects for a UDP socket toward a public address. A UDP ``connect``
  sends no packets; it only fixes the route lookup.
- The default gateway is read from ``/proc/net/route`` on Linux. On
  other platforms it is reported as unknown: the portable standard
  library offers no way to read it, and platform adapters outside the
  core may fill it in.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field


@dataclass
class InterfaceInfo:
    name: str
    index: int | None = None
    addresses: list[str] = field(default_factory=list)
    is_loopback: bool = False


@dataclass
class NetworkInventory:
    hostname: str
    interfaces: list[InterfaceInfo] = field(default_factory=list)
    local_addresses: list[str] = field(default_factory=list)
    outbound_ipv4: str | None = None
    default_gateway: str | None = None
    notes: list[str] = field(default_factory=list)


def _gateway_linux() -> str | None:
    """Default gateway from /proc/net/route, or None.

    The gateway is stored as a little-endian hexadecimal IPv4 address
    on the route whose destination is 00000000.
    """
    try:
        with open("/proc/net/route", encoding="ascii") as handle:
            lines = handle.readlines()
    except OSError:
        return None
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "00000000":
            hex_gateway = parts[2]
            try:
                packed = bytes.fromhex(hex_gateway)
            except ValueError:
                return None
            if len(packed) == 4:
                return socket.inet_ntoa(packed[::-1])
    return None


def _outbound_ipv4(probe_host: str) -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((probe_host, 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def list_interfaces(probe_host: str = "8.8.8.8") -> NetworkInventory:
    """Inventory the local network interfaces as far as the stdlib allows."""
    inventory = NetworkInventory(hostname=socket.gethostname())
    notes = inventory.notes

    try:
        infos = socket.getaddrinfo(inventory.hostname, None)
        for info in infos:
            address = info[4][0]
            if address not in inventory.local_addresses:
                inventory.local_addresses.append(address)
    except OSError:
        notes.append("The local hostname could not be resolved, so local addresses are unknown.")

    if hasattr(socket, "if_nameindex"):
        try:
            for index, name in socket.if_nameindex():
                inventory.interfaces.append(
                    InterfaceInfo(
                        name=name,
                        index=index,
                        is_loopback=name in ("lo", "lo0"),
                    )
                )
        except OSError:
            notes.append("Interface enumeration failed on this platform.")
    else:
        notes.append("This platform does not provide socket.if_nameindex(); interface names are unknown.")
    if inventory.interfaces:
        notes.append(
            "Per-interface addresses are not available from the Python standard library; "
            "local addresses are listed at machine level instead."
        )
        for iface in inventory.interfaces:
            if iface.is_loopback:
                iface.addresses = [a for a in inventory.local_addresses if a.startswith("127.") or a == "::1"]

    inventory.outbound_ipv4 = _outbound_ipv4(probe_host)
    if inventory.outbound_ipv4 is None:
        notes.append("No outbound IPv4 route could be determined.")

    gateway = _gateway_linux()
    if gateway is not None:
        inventory.default_gateway = gateway
    else:
        notes.append(
            "The default gateway is read from /proc/net/route on Linux only; "
            "it is unknown on this platform."
        )
    return inventory
