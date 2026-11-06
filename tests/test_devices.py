import sqlite3

import pytest


def test_create_device_defaults(isolated_db):
    device = isolated_db.create_device("Paris", "FW-PAR-EDGE1", "palo_alto", "10.1.2.3")

    assert device.site == "Paris"
    assert device.ssh_port == 22
    assert device.object_prefix == ""
    assert device.group_prefix == ""
    assert isolated_db.get_device(device.id) == device


def test_list_devices_ordered_by_site_then_name(isolated_db):
    isolated_db.create_device("Bordeaux", "FW-BDX-2", "fortinet", "10.2.0.2")
    isolated_db.create_device("Bordeaux", "FW-BDX-1", "fortinet", "10.2.0.1")
    isolated_db.create_device("Paris", "FW-PAR-1", "palo_alto", "10.1.0.1")

    names = [(d.site, d.name) for d in isolated_db.list_devices()]
    assert names == [("Bordeaux", "FW-BDX-1"), ("Bordeaux", "FW-BDX-2"), ("Paris", "FW-PAR-1")]


def test_list_sites_distinct_and_sorted(isolated_db):
    isolated_db.create_device("Paris", "FW-PAR-1", "palo_alto", "10.1.0.1")
    isolated_db.create_device("Bordeaux", "FW-BDX-1", "fortinet", "10.2.0.1")
    isolated_db.create_device("Paris", "FW-PAR-2", "palo_alto", "10.1.0.2")

    assert isolated_db.list_sites() == ["Bordeaux", "Paris"]


def test_update_device_changes_fields(isolated_db):
    device = isolated_db.create_device("Paris", "FW-PAR-1", "palo_alto", "10.1.0.1")

    isolated_db.update_device(
        device.id, "Paris", "FW-PAR-1", "palo_alto", "10.1.0.9", ssh_port=2222,
        object_prefix="IOC-PAR", group_prefix="IOC-PAR-GRP",
    )

    updated = isolated_db.get_device(device.id)
    assert updated.host == "10.1.0.9"
    assert updated.ssh_port == 2222
    assert updated.object_prefix == "IOC-PAR"
    assert updated.group_prefix == "IOC-PAR-GRP"


def test_create_device_rejects_duplicate_name_within_same_site(isolated_db):
    isolated_db.create_device("Paris", "FW-PAR-1", "palo_alto", "10.1.0.1")

    with pytest.raises(sqlite3.IntegrityError):
        isolated_db.create_device("Paris", "FW-PAR-1", "fortinet", "10.1.0.2")


def test_create_device_allows_same_name_on_different_sites(isolated_db):
    isolated_db.create_device("Paris", "FW-EDGE1", "palo_alto", "10.1.0.1")
    isolated_db.create_device("Bordeaux", "FW-EDGE1", "fortinet", "10.2.0.1")

    assert len(isolated_db.list_devices()) == 2


def test_delete_device_removes_row(isolated_db):
    device = isolated_db.create_device("Paris", "FW-PAR-1", "palo_alto", "10.1.0.1")

    isolated_db.delete_device(device.id)

    assert isolated_db.get_device(device.id) is None
    assert isolated_db.list_devices() == []
