"""Génération des commandes CLI Palo Alto (PAN-OS)."""
from typing import Iterable, Optional

from generators.base import object_name
from validators import ParsedValue


def generate(prefix: str, group_name: str, values: Iterable[ParsedValue], vsys: Optional[str] = None) -> str:
    """Génère les commandes `set address` / `set address-group`.

    `vsys` fixe le contexte PAN-OS quand le firewall a plusieurs vsys :
    - None (défaut) : pas de préfixe, comportement mono-vsys historique.
    - "shared" : préfixe `set shared ...` — objets visibles par tous les vsys.
    - toute autre valeur : préfixe `set vsys <nom> ...` — objets scopés à ce vsys.
    L'objet et le groupe qui le référence doivent être dans le même scope (un groupe `shared`
    ne peut pas référencer un objet local à un vsys, et inversement), donc le préfixe
    s'applique identiquement aux deux types de commande.
    """
    scope_prefix = ""
    if vsys == "shared":
        scope_prefix = "shared "
    elif vsys:
        scope_prefix = f"vsys {vsys} "

    lines: list[str] = []
    members: list[str] = []

    for parsed in values:
        name = object_name(prefix, parsed)
        members.append(name)
        if parsed.kind == "fqdn":
            lines.append(f"set {scope_prefix}address {name} fqdn {parsed.ip}")
        else:
            lines.append(f"set {scope_prefix}address {name} ip-netmask {parsed.ip}/{parsed.cidr_suffix}")

    for name in members:
        lines.append(f"set {scope_prefix}address-group {group_name} static {name}")

    return "\n".join(lines)
