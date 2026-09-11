"""Génération des commandes CLI FortiGate (FortiOS)."""
from typing import Iterable

from generators.base import netmask_from_prefix, object_name
from validators import ParsedValue


def generate(prefix: str, group_name: str, values: Iterable[ParsedValue]) -> str:
    values = list(values)
    lines: list[str] = ["config firewall address"]
    members: list[str] = []

    for parsed in values:
        name = object_name(prefix, parsed)
        members.append(name)
        lines.append(f'    edit "{name}"')
        if parsed.kind == "fqdn":
            lines.append("        set type fqdn")
            lines.append(f"        set fqdn {parsed.ip}")
        else:
            lines.append(f"        set subnet {parsed.ip} {netmask_from_prefix(parsed.cidr_suffix)}")
        lines.append("    next")
    lines.append("end")

    lines.append("config firewall addrgrp")
    lines.append(f'    edit "{group_name}"')
    for name in members:
        lines.append(f'        append member "{name}"')
    lines.append("    next")
    lines.append("end")

    return "\n".join(lines)
