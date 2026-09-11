from generators import cisco_asa, fortinet, palo_alto
from validators import parse_value


def _values(*raws):
    return [parse_value(r) for r in raws]


def test_palo_alto_ip_and_group():
    out = palo_alto.generate("IOC-case-Test", "IOC-case-Test", _values("1.2.3.4"))
    assert "set address IOC-case-Test_1.2.3.4 ip-netmask 1.2.3.4/32" in out
    assert "set address-group IOC-case-Test static IOC-case-Test_1.2.3.4" in out


def test_palo_alto_cidr_and_fqdn():
    out = palo_alto.generate("P", "P", _values("10.0.0.0/24", "example.com"))
    assert "set address P_10.0.0.0-24 ip-netmask 10.0.0.0/24" in out
    assert "set address P_example.com fqdn example.com" in out


def test_fortinet_cidr_uses_netmask():
    out = fortinet.generate("P", "P", _values("10.0.0.0/24"))
    assert "set subnet 10.0.0.0 255.255.255.0" in out
    assert 'append member "P_10.0.0.0-24"' in out


def test_fortinet_fqdn():
    out = fortinet.generate("P", "P", _values("example.com"))
    assert "set type fqdn" in out
    assert "set fqdn example.com" in out


def test_cisco_asa_host_for_single_ip_and_subnet_for_cidr():
    out = cisco_asa.generate("P", "GRP", _values("8.8.8.8", "10.0.0.0/24"))
    assert " host 8.8.8.8" in out
    assert " subnet 10.0.0.0 255.255.255.0" in out
    assert "object-group network GRP" in out
    assert " network-object object P_8.8.8.8" in out
    assert " network-object object P_10.0.0.0-24" in out


def test_cisco_asa_fqdn():
    out = cisco_asa.generate("P", "GRP", _values("example.com"))
    assert " fqdn example.com" in out
