import sqlite3

import pytest


def test_update_case_renames_and_changes_prefix(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.update_case(case.id, "Renomme", "IOC-case-Renomme")

    updated = isolated_db.get_case(case.id)
    assert updated.name == "Renomme"
    assert updated.prefix == "IOC-case-Renomme"


def test_create_case_defaults_group_prefix_to_prefix(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    assert case.group_prefix == "IOC-case-Test"
    assert isolated_db.get_case(case.id).group_prefix == "IOC-case-Test"


def test_create_case_with_distinct_group_prefix(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test", group_prefix="IOC-grp-Test")
    assert case.prefix == "IOC-case-Test"
    assert case.group_prefix == "IOC-grp-Test"
    assert isolated_db.get_case(case.id).group_prefix == "IOC-grp-Test"


def test_update_case_can_set_distinct_group_prefix(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.update_case(case.id, "Test", "IOC-case-Test", group_prefix="IOC-grp-Test")

    updated = isolated_db.get_case(case.id)
    assert updated.prefix == "IOC-case-Test"
    assert updated.group_prefix == "IOC-grp-Test"


def test_update_case_rejects_duplicate_name(isolated_db):
    isolated_db.create_case("CasA", "IOC-case-A")
    case_b = isolated_db.create_case("CasB", "IOC-case-B")

    with pytest.raises(sqlite3.IntegrityError):
        isolated_db.update_case(case_b.id, "CasA", "IOC-case-B")


def test_delete_case_cascades_to_entries(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj1")])
    assert isolated_db.count_entries_for_case(case.id) == 1

    isolated_db.delete_case(case.id)

    assert isolated_db.get_case(case.id) is None
    with isolated_db.get_conn() as conn:
        remaining = conn.execute("SELECT COUNT(*) AS n FROM entries WHERE case_id = ?", (case.id,)).fetchone()
        assert remaining["n"] == 0


def test_count_entries_for_case(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    assert isolated_db.count_entries_for_case(case.id) == 0

    isolated_db.add_entries(
        case.id,
        "palo_alto",
        [("1.2.3.4", "1.2.3.4", False, "obj1"), ("5.6.7.8", "5.6.7.8", False, "obj2")],
    )
    assert isolated_db.count_entries_for_case(case.id) == 2


def test_archive_entry_marks_unblocked_and_excludes_from_active_dedup(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj1")])
    entry_id = isolated_db.list_history()[0]["entry_id"]

    assert isolated_db.existing_normalized_for_case(case.id, "palo_alto") == {"1.2.3.4"}

    isolated_db.archive_entry(entry_id)

    row = isolated_db.list_history()[0]
    assert row["unblocked_at"] is not None
    # Une fois archivée, la valeur ne doit plus être vue comme "déjà bloquée" -> on peut la rebloquer.
    assert isolated_db.existing_normalized_for_case(case.id, "palo_alto") == set()


def test_reblock_after_archive_does_not_violate_unique_index(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj1")])
    entry_id = isolated_db.list_history()[0]["entry_id"]
    isolated_db.archive_entry(entry_id)

    # Ne doit PAS lever IntegrityError malgré la même clé (case_id, firewall, normalized).
    isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj2")])

    assert isolated_db.count_entries_for_case(case.id) == 2


def test_unarchive_entry_restores_active_status(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj1")])
    entry_id = isolated_db.list_history()[0]["entry_id"]

    isolated_db.archive_entry(entry_id)
    isolated_db.unarchive_entry(entry_id)

    assert isolated_db.list_history()[0]["unblocked_at"] is None


def test_delete_entry_removes_row(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.add_entries(case.id, "palo_alto", [("1.2.3.4", "1.2.3.4", False, "obj1")])
    entry_id = isolated_db.list_history()[0]["entry_id"]

    isolated_db.delete_entry(entry_id)

    assert isolated_db.list_history() == []


def test_list_history_status_filter(isolated_db):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    isolated_db.add_entries(
        case.id,
        "palo_alto",
        [("1.2.3.4", "1.2.3.4", False, "obj1"), ("5.6.7.8", "5.6.7.8", False, "obj2")],
    )
    rows = isolated_db.list_history()
    archived_id = next(r["entry_id"] for r in rows if r["value"] == "1.2.3.4")
    isolated_db.archive_entry(archived_id)

    assert {r["value"] for r in isolated_db.list_history(status="active")} == {"5.6.7.8"}
    assert {r["value"] for r in isolated_db.list_history(status="archived")} == {"1.2.3.4"}
    assert {r["value"] for r in isolated_db.list_history(status="all")} == {"1.2.3.4", "5.6.7.8"}
