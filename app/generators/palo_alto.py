"""Génération des commandes CLI Palo Alto (PAN-OS)."""
from typing import Iterable

from generators.base import object_name
from validators import ParsedValue


def generate(prefix: str, group_name: str, values: Iterable[ParsedValue]) -> str:
    lines: list[str] = []
    members: list[str] = []

    for parsed in values:
        name = object_name(prefix, parsed)
        members.append(name)
        if parsed.kind == "fqdn":
            lines.append(f"set address {name} fqdn {parsed.ip}")
        else:
            lines.append(f"set address {name} ip-netmask {parsed.ip}/{parsed.cidr_suffix}")

    for name in members:
        lines.append(f"set address-group {group_name} static {name}")

    return "\n".join(lines)
