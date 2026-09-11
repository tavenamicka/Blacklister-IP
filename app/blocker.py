"""Logique métier : parsing, dédup (intra-cas / inter-cas), génération et sauvegarde."""
from dataclasses import dataclass, field

import db
from generators import cisco_asa, fortinet, palo_alto
from generators.base import Generator, object_name
from validators import ParsedValue, parse_lines

GENERATORS: dict[str, Generator] = {
    "palo_alto": palo_alto.generate,
    "fortinet": fortinet.generate,
    "cisco_asa": cisco_asa.generate,
}


@dataclass
class FirewallResult:
    firewall: str
    new_values: list[ParsedValue] = field(default_factory=list)
    duplicates_in_case: list[str] = field(default_factory=list)
    cross_case_warnings: list[tuple[str, str]] = field(default_factory=list)  # (valeur, autre_cas)
    invalid: list[str] = field(default_factory=list)
    commands: str = ""


def process(case: db.Case, firewall: str, raw_text: str) -> FirewallResult:
    result = FirewallResult(firewall=firewall)
    parsed_list = parse_lines(raw_text)

    # Préchargement en 2 requêtes (au lieu d'aller-retours DB par ligne collée).
    existing_in_case = db.existing_normalized_for_case(case.id, firewall)
    other_case_by_normalized = db.normalized_case_map(firewall, exclude_case_id=case.id)

    seen_in_batch: set[str] = set()
    for parsed in parsed_list:
        if parsed.kind == "invalid":
            result.invalid.append(parsed.raw)
            continue

        key = parsed.normalized
        if key in seen_in_batch or key in existing_in_case:
            result.duplicates_in_case.append(parsed.raw)
            continue

        other_case = other_case_by_normalized.get(key)
        if other_case:
            result.cross_case_warnings.append((parsed.raw, other_case))

        seen_in_batch.add(key)
        result.new_values.append(parsed)

    group_name = case.group_prefix
    if result.new_values:
        result.commands = GENERATORS[firewall](case.prefix, group_name, result.new_values)

    return result


def save(case: db.Case, firewall: str, values: list[ParsedValue]) -> None:
    items = [
        (parsed.raw.strip(), parsed.normalized, parsed.kind == "fqdn", object_name(case.prefix, parsed))
        for parsed in values
    ]
    db.add_entries(case.id, firewall, items)
