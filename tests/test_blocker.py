import sqlite3

import blocker
import pytest


def test_process_dedups_within_batch_and_flags_invalid(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    result = blocker.process(case, "palo_alto", "1.2.3.4\n1.2.3.4\nnotanip\n")

    assert [v.raw for v in result.new_values] == ["1.2.3.4"]
    assert result.duplicates_in_case == ["1.2.3.4"]
    assert result.invalid == ["notanip"]


def test_save_then_reprocess_flags_as_duplicate_in_case(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    result = blocker.process(case, "palo_alto", "1.2.3.4")
    blocker.save(case, "palo_alto", result.new_values)

    result2 = blocker.process(case, "palo_alto", "1.2.3.4")
    assert result2.new_values == []
    assert result2.duplicates_in_case == ["1.2.3.4"]


def test_process_uses_distinct_group_prefix_for_group_name(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test", group_prefix="IOC-grp-Test")
    result = blocker.process(case, "palo_alto", "1.2.3.4")

    assert "set address IOC-case-Test_1.2.3.4 ip-netmask 1.2.3.4/32" in result.commands
    assert "set address-group IOC-grp-Test static IOC-case-Test_1.2.3.4" in result.commands


def test_process_forwards_options_to_generator(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    result = blocker.process(case, "palo_alto", "1.2.3.4", options={"vsys": "shared"})

    assert "set shared address IOC-case-Test_1.2.3.4 ip-netmask 1.2.3.4/32" in result.commands


def test_cross_case_warning_does_not_block_new_case(isolated_db):
    case1 = isolated_db.create_case("Case1", "IOC-case-1")
    case2 = isolated_db.create_case("Case2", "IOC-case-2")

    r1 = blocker.process(case1, "palo_alto", "1.2.3.4")
    blocker.save(case1, "palo_alto", r1.new_values)

    r2 = blocker.process(case2, "palo_alto", "1.2.3.4")
    assert r2.cross_case_warnings == [("1.2.3.4", "Case1")]
    assert [v.raw for v in r2.new_values] == ["1.2.3.4"]


def test_save_uses_a_single_transaction_for_the_whole_batch(isolated_db, monkeypatch):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    result = blocker.process(case, "palo_alto", "1.2.3.4\n5.6.7.8\n9.10.11.12")

    connect_calls = []
    original_connect = isolated_db.sqlite3.connect

    def counting_connect(*args, **kwargs):
        connect_calls.append(1)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(isolated_db.sqlite3, "connect", counting_connect)

    blocker.save(case, "palo_alto", result.new_values)

    assert len(connect_calls) == 1


def test_db_unique_constraint_blocks_direct_duplicate(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj1")])

    with pytest.raises(sqlite3.IntegrityError):
        isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj2")])


def test_process_uses_device_prefixes_and_extra_options(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    device = isolated_db.create_device(
        "Paris", "FW-PAR", "palo_alto", "10.1.0.1", object_prefix="IOC-PAR", group_prefix="IOC-PAR-GRP",
        extra_options='{"vsys": "shared"}',
    )

    result = blocker.process(case, "palo_alto", "1.2.3.4", device=device)

    assert "set shared address IOC-PAR_1.2.3.4 ip-netmask 1.2.3.4/32" in result.commands
    assert "set shared address-group IOC-PAR-GRP static IOC-PAR_1.2.3.4" in result.commands
    assert result.device == device


def test_process_falls_back_to_case_prefix_when_device_has_none(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    device = isolated_db.create_device("Paris", "FW-PAR", "palo_alto", "10.1.0.1")

    result = blocker.process(case, "palo_alto", "1.2.3.4", device=device)

    assert "set address IOC-case-Test_1.2.3.4 ip-netmask 1.2.3.4/32" in result.commands


def test_dedup_is_scoped_per_device_not_just_per_firewall(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    paris = isolated_db.create_device("Paris", "FW-PAR", "palo_alto", "10.1.0.1")
    bordeaux = isolated_db.create_device("Bordeaux", "FW-BDX", "palo_alto", "10.2.0.1")

    r1 = blocker.process(case, "palo_alto", "1.2.3.4", device=paris)
    blocker.save(case, "palo_alto", r1.new_values, device=paris)

    # Même IP, même cas, même marque, mais device différent -> pas un doublon.
    r2 = blocker.process(case, "palo_alto", "1.2.3.4", device=bordeaux)
    assert [v.raw for v in r2.new_values] == ["1.2.3.4"]
    assert r2.duplicates_in_case == []

    # Ressaisie sur le même device Paris -> bien détectée comme doublon.
    r3 = blocker.process(case, "palo_alto", "1.2.3.4", device=paris)
    assert r3.duplicates_in_case == ["1.2.3.4"]


def test_process_ignores_unsupported_extra_options_for_target_firewall(isolated_db):
    """extra_options est un JSON libre par device (app/db.py) : une clé qui n'a de sens que pour
    une autre marque (ex. 'vsys', propre à Palo Alto) ne doit pas faire planter un générateur qui
    n'accepte pas **options (fortinet.generate n'a pas de **kwargs)."""
    case = isolated_db.create_case("Test", "IOC-case-Test")
    device = isolated_db.create_device(
        "Paris", "FW-PAR", "fortinet", "10.1.0.1", extra_options='{"vsys": "shared"}',
    )

    result = blocker.process(case, "fortinet", "1.2.3.4", device=device)

    assert "1.2.3.4" in result.commands


def test_save_persists_device_id_and_history_shows_device(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    device = isolated_db.create_device("Paris", "FW-PAR", "palo_alto", "10.1.0.1")

    result = blocker.process(case, "palo_alto", "1.2.3.4", device=device)
    blocker.save(case, "palo_alto", result.new_values, device=device)

    entry = isolated_db.list_history()[0]
    assert entry.device_name == "FW-PAR"
    assert entry.device_site == "Paris"
