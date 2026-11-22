import ipaddress

from netscope_core.interfaces import list_interfaces


def test_inventory_shape():
    inventory = list_interfaces()
    assert inventory.hostname  # a non-empty string
    assert isinstance(inventory.interfaces, list)
    assert isinstance(inventory.local_addresses, list)
    assert isinstance(inventory.notes, list)


def test_inventory_addresses_are_valid_when_present():
    inventory = list_interfaces()
    for address in inventory.local_addresses:
        ipaddress.ip_address(address)  # raises if malformed
    if inventory.outbound_ipv4 is not None:
        ipaddress.ip_address(inventory.outbound_ipv4)
    if inventory.default_gateway is not None:
        gateway = ipaddress.ip_address(inventory.default_gateway)
        assert gateway.version == 4
