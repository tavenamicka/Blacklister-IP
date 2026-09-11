"""Vérifie que les bases créées sous le schéma v1 (avant l'ajout de l'archivage) migrent sans perte."""
import sqlite3

import db


def _create_v1_database(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.execute(
        """
        CREATE TABLE cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            prefix TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            firewall TEXT NOT NULL,
            value TEXT NOT NULL,
            normalized TEXT NOT NULL,
            is_fqdn INTEGER NOT NULL,
            object_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(case_id, firewall, normalized)
        )
        """
    )
    conn.execute(
        "INSERT INTO cases (name, prefix, created_at) VALUES ('iTrust', 'IOC-case-iTrust', '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO entries (case_id, firewall, value, normalized, is_fqdn, object_name, created_at) "
        "VALUES (1, 'palo_alto', '1.2.3.4', '1.2.3.4', 0, 'IOC-case-iTrust_1.2.3.4', '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()


def test_migration_preserves_cases_and_entries_and_adds_unblocked_at(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "app_root", lambda: tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _create_v1_database(data_dir / "blacklister.db")

    db.init_db()

    cases = db.list_cases()
    assert [c.name for c in cases] == ["iTrust"]

    history = db.list_history()
    assert len(history) == 1
    assert history[0]["value"] == "1.2.3.4"
    assert history[0]["unblocked_at"] is None

    assert cases[0].group_prefix == "IOC-case-iTrust"  # backfill = prefix pour les cas déjà créés

    with db.get_conn() as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        assert version == 3
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(entries)").fetchall()}
        assert "unblocked_at" in cols
        case_cols = {r["name"] for r in conn.execute("PRAGMA table_info(cases)").fetchall()}
        assert "group_prefix" in case_cols
