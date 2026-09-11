import sqlite3

import pytest

import blocker


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
