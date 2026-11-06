"""Logique métier : parsing, dédup (intra-cas / inter-cas), génération et sauvegarde."""
import inspect
import json
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
    device: db.Device | None = None
    new_values: list[ParsedValue] = field(default_factory=list)
    duplicates_in_case: list[str] = field(default_factory=list)
    cross_case_warnings: list[tuple[str, str]] = field(default_factory=list)  # (valeur, autre_cas)
    invalid: list[str] = field(default_factory=list)
    commands: str = ""


def _effective_prefixes(case: db.Case, device: db.Device | None) -> tuple[str, str]:
    """Un device avec préfixe propre l'emporte sur celui du cas (sinon on retombe sur le cas,
    comme avant l'introduction du registre de pare-feu)."""
    object_prefix = device.object_prefix if device and device.object_prefix else case.prefix
    group_prefix = device.group_prefix if device and device.group_prefix else case.group_prefix
    return object_prefix, group_prefix


def _device_options(device: db.Device | None) -> dict:
    if not device or not device.extra_options:
        return {}
    try:
        return json.loads(device.extra_options)
    except json.JSONDecodeError:
        return {}


def _filtered_options(firewall: str, options: dict) -> dict:
    """Ne garde que les clés que GENERATORS[firewall] accepte réellement : extra_options d'un
    device est un JSON libre (cf. app/db.py), rien ne garantit qu'il ne contient qu'une clé
    pertinente pour la marque de ce device (ex. 'vsys' n'a de sens que pour Palo Alto) — sans ce
    filtre, un générateur qui n'accepte pas **options (fortinet.generate, cisco_asa.generate)
    lèverait un TypeError."""
    accepted = set(inspect.signature(GENERATORS[firewall]).parameters) - {"prefix", "group_name", "values"}
    return {k: v for k, v in options.items() if k in accepted}


def process(
    case: db.Case, firewall: str, raw_text: str, device: db.Device | None = None, options: dict | None = None,
) -> FirewallResult:
    """`device` : pare-feu physique précis (registre `devices`) ciblé par cette génération — fixe
    les préfixes et options propres à ce device (ex. vsys Palo Alto) et scope la dédup à CE device
    (deux sites de même marque ne se bloquent pas l'un l'autre). None = mode générique historique,
    sans device (dédup au niveau de la marque, comme avant)."""
    result = FirewallResult(firewall=firewall, device=device)
    parsed_list = parse_lines(raw_text)
    device_id = device.id if device else None

    # Préchargement en 2 requêtes (au lieu d'aller-retours DB par ligne collée).
    existing_in_case = db.existing_normalized_for_case(case.id, firewall, device_id)
    other_case_by_normalized = db.normalized_case_map(firewall, exclude_case_id=case.id, device_id=device_id)

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

    object_prefix, group_prefix = _effective_prefixes(case, device)
    merged_options = _filtered_options(firewall, {**_device_options(device), **(options or {})})
    if result.new_values:
        result.commands = GENERATORS[firewall](object_prefix, group_prefix, result.new_values, **merged_options)

    return result


def save(case: db.Case, firewall: str, values: list[ParsedValue], device: db.Device | None = None) -> None:
    object_prefix, _ = _effective_prefixes(case, device)
    items = [
        (parsed.raw.strip(), parsed.normalized, parsed.kind == "fqdn", object_name(object_prefix, parsed))
        for parsed in values
    ]
    db.add_entries(case.id, firewall, items, device.id if device else None)
