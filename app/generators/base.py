"""Utilitaires communs aux générateurs de commandes CLI."""
import re
from collections.abc import Iterable
from typing import Protocol

from validators import ParsedValue

_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_.-]")


class Generator(Protocol):
    """Contrat que doit respecter le module `generate()` de chaque pare-feu (cf. generators/palo_alto.py etc.).
    `**options` : options propres à un pare-feu donné (ex. `vsys` pour Palo Alto) — les générateurs
    qui n'en ont pas besoin n'en déclarent simplement aucune."""

    def __call__(self, prefix: str, group_name: str, values: Iterable[ParsedValue], **options) -> str: ...


def object_name(prefix: str, parsed: ParsedValue) -> str:
    """Nom d'objet réseau : <prefix>_<valeur>, caractères non supportés remplacés par '-'."""
    suffix = _SANITIZE_RE.sub("-", parsed.normalized)
    return f"{prefix}_{suffix}"


def netmask_from_prefix(prefix_len: int) -> str:
    """Convertit une longueur de préfixe CIDR (ex: 24) en masque décimal pointé."""
    bits = "1" * prefix_len + "0" * (32 - prefix_len)
    octets = [bits[i : i + 8] for i in range(0, 32, 8)]
    return ".".join(str(int(o, 2)) for o in octets)
