"""Validation et classification des valeurs saisies (IPv4/CIDR ou FQDN)."""
import re
from dataclasses import dataclass
from typing import Optional

_IPV4_OCTET = r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
IPV4_RE = re.compile(rf"^{_IPV4_OCTET}(?:\.{_IPV4_OCTET}){{3}}$")
CIDR_RE = re.compile(rf"^({_IPV4_OCTET}(?:\.{_IPV4_OCTET}){{3}})/(\d{{1,2}})$")
FQDN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)


@dataclass
class ParsedValue:
    raw: str
    kind: str  # "ip" | "fqdn" | "invalid"
    ip: Optional[str] = None
    prefix_len: Optional[int] = None

    @property
    def normalized(self) -> str:
        """Valeur utilisée comme clé de dédup / suffixe de nom d'objet."""
        if self.kind == "ip" and self.prefix_len is not None:
            return f"{self.ip}-{self.prefix_len}"
        if self.kind == "ip":
            return self.ip
        return self.raw.lower()

    @property
    def cidr_suffix(self) -> int:
        return self.prefix_len if self.prefix_len is not None else 32


def parse_value(raw: str) -> ParsedValue:
    value = raw.strip()
    if not value:
        return ParsedValue(raw=raw, kind="invalid")

    cidr_match = CIDR_RE.match(value)
    if cidr_match:
        prefix_len = int(cidr_match.group(2))
        if 0 <= prefix_len <= 32:
            # "/32" désigne un hôte unique, exactement comme l'IP sans suffixe : on les traite
            # comme la même valeur pour que la dédup les reconnaisse comme identiques.
            normalized_prefix_len = prefix_len if prefix_len != 32 else None
            return ParsedValue(raw=raw, kind="ip", ip=cidr_match.group(1), prefix_len=normalized_prefix_len)
        return ParsedValue(raw=raw, kind="invalid")

    if IPV4_RE.match(value):
        return ParsedValue(raw=raw, kind="ip", ip=value, prefix_len=None)

    if FQDN_RE.match(value) and not value.rsplit(".", 1)[-1].isdigit():
        # Le dernier label (TLD) ne doit pas être purement numérique, sinon une IP
        # mal formée comme "999.999.999.999" serait classée à tort comme un FQDN valide.
        return ParsedValue(raw=raw, kind="fqdn", ip=value)

    return ParsedValue(raw=raw, kind="invalid")


def parse_lines(text: str) -> list[ParsedValue]:
    lines = [l.strip() for l in text.splitlines()]
    return [parse_value(l) for l in lines if l.strip()]
