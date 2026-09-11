"""Génération des commandes CLI Cisco ASA (reprend Gen_CMD_ListIP_ITRUST_NBR_V3.ps1)."""
from typing import Iterable

from generators.base import netmask_from_prefix, object_name
from validators import ParsedValue


def generate(prefix: str, group_name: str, values: Iterable[ParsedValue]) -> str:
    values = list(values)
    lines: list[str] = []
    members: list[str] = []

    for parsed in values:
        name = object_name(prefix, parsed)
        members.append(name)
        lines.append(f"object network {name}")
        if parsed.kind == "fqdn":
            lines.append(f" fqdn {parsed.ip}")
        elif parsed.cidr_suffix != 32:
            lines.append(f" subnet {parsed.ip} {netmask_from_prefix(parsed.cidr_suffix)}")
        else:
            lines.append(f" host {parsed.ip}")
        lines.append(f" description {name}")
        lines.append("exit")
        lines.append("")

    lines.append(f"object-group network {group_name}")
    for name in members:
        lines.append(f" network-object object {name}")
    lines.append("exit")

    return "\n".join(lines)
