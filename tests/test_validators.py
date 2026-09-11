from validators import parse_lines, parse_value


def test_parse_plain_ipv4():
    p = parse_value("172.71.151.78")
    assert p.kind == "ip"
    assert p.ip == "172.71.151.78"
    assert p.prefix_len is None
    assert p.cidr_suffix == 32
    assert p.normalized == "172.71.151.78"


def test_parse_cidr():
    p = parse_value("10.0.0.5/24")
    assert p.kind == "ip"
    assert p.ip == "10.0.0.5"
    assert p.prefix_len == 24
    assert p.cidr_suffix == 24
    assert p.normalized == "10.0.0.5-24"


def test_parse_cidr_prefix_out_of_range_is_invalid():
    assert parse_value("10.0.0.5/33").kind == "invalid"
    assert parse_value("10.0.0.5/99").kind == "invalid"


def test_slash_32_is_equivalent_to_plain_ip():
    # "1.2.3.4" et "1.2.3.4/32" désignent le même hôte : la dédup doit les traiter comme identiques.
    plain = parse_value("1.2.3.4")
    slash32 = parse_value("1.2.3.4/32")
    assert plain.normalized == slash32.normalized == "1.2.3.4"
    assert slash32.cidr_suffix == 32


def test_parse_fqdn():
    p = parse_value("example.com")
    assert p.kind == "fqdn"
    assert p.normalized == "example.com"


def test_parse_fqdn_normalized_is_case_insensitive():
    p = parse_value("Example.COM")
    assert p.kind == "fqdn"
    assert p.normalized == "example.com"


def test_malformed_ip_with_out_of_range_octets_is_invalid_not_fqdn():
    # Régression : "999.999.999.999" matchait autrefois la regex FQDN (TLD purement
    # numérique non exclu) et était bloqué comme un nom de domaine au lieu d'être rejeté.
    p = parse_value("999.999.999.999")
    assert p.kind == "invalid"


def test_parse_invalid_values():
    for bad in ["bad_ip_999", "", "   ", "-not-a-domain", "no spaces allowed.com"]:
        assert parse_value(bad).kind == "invalid", bad


def test_parse_lines_skips_blank_lines():
    values = parse_lines("172.71.151.78\n\n   \nexample.com\n")
    assert [v.raw for v in values] == ["172.71.151.78", "example.com"]
