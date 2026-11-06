"""Accès SQLite : cas, pare-feu cibles, entrées bloquées. DB stockée à côté de l'exe (portable)."""
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 5

FIREWALLS = ("palo_alto", "fortinet", "cisco_asa")

FIREWALL_LABELS = {
    "palo_alto": "Palo Alto",
    "fortinet": "Fortinet",
    "cisco_asa": "Cisco ASA",
}


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def db_path() -> Path:
    data_dir = app_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "blacklister.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            current_version = SCHEMA_VERSION  # base neuve : créée ci-dessous directement à jour
        else:
            current_version = row["version"]

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                prefix TEXT NOT NULL,
                group_prefix TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        # Forme à jour (v2) : pas de UNIQUE(case_id, firewall, normalized) au niveau table — une
        # entrée archivée (unblocked_at renseigné) ne doit pas empêcher de rebloquer la même valeur
        # plus tard. L'unicité "actif" est appliquée par l'index partiel ci-dessous.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                firewall TEXT NOT NULL,
                value TEXT NOT NULL,
                normalized TEXT NOT NULL,
                is_fqdn INTEGER NOT NULL,
                object_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                unblocked_at TEXT,
                device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL
            )
            """
        )

        if current_version < 2:
            _migrate_v1_to_v2(conn)
            current_version = 2
            conn.execute("UPDATE schema_version SET version = ?", (current_version,))

        if current_version < 3:
            _migrate_v2_to_v3(conn)
            current_version = 3
            conn.execute("UPDATE schema_version SET version = ?", (current_version,))

        # Registre des pare-feu physiques (site/pôle, host SSH...). Table neuve : pas de backfill
        # nécessaire, CREATE TABLE IF NOT EXISTS suffit pour les bases neuves comme pour les anciennes.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,
                name TEXT NOT NULL,
                firewall TEXT NOT NULL,
                host TEXT NOT NULL,
                ssh_port INTEGER NOT NULL DEFAULT 22,
                object_prefix TEXT NOT NULL DEFAULT '',
                group_prefix TEXT NOT NULL DEFAULT '',
                extra_options TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(site, name)
            )
            """
        )
        if current_version < 4:
            current_version = 4
            conn.execute("UPDATE schema_version SET version = ?", (current_version,))

        if current_version < 5:
            _migrate_v4_to_v5(conn)
            current_version = 5
            conn.execute("UPDATE schema_version SET version = ?", (current_version,))

        # Recréé à chaque démarrage (pas IF NOT EXISTS) : garantit que la définition de l'index
        # reflète toujours le COALESCE ci-dessous, même sur une base migrée depuis une version
        # antérieure à l'ajout de device_id.
        conn.execute("DROP INDEX IF EXISTS idx_entries_active_unique")
        conn.execute(
            "CREATE UNIQUE INDEX idx_entries_active_unique "
            "ON entries(case_id, firewall, COALESCE(device_id, -1), normalized) WHERE unblocked_at IS NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entries_lookup ON entries(firewall, normalized)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_case ON entries(case_id)")


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """v1 -> v2 : ajoute entries.unblocked_at et retire l'ancienne contrainte UNIQUE globale
    (recréation de table, SQLite ne sait pas la retirer via ALTER TABLE)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(entries)").fetchall()}
    if "unblocked_at" in cols:
        return  # déjà migré (ne devrait pas arriver vu le garde-fou sur schema_version, mais sans risque)

    conn.execute("ALTER TABLE entries RENAME TO entries_v1")
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
            unblocked_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO entries (id, case_id, firewall, value, normalized, is_fqdn, object_name, created_at) "
        "SELECT id, case_id, firewall, value, normalized, is_fqdn, object_name, created_at FROM entries_v1"
    )
    conn.execute("DROP TABLE entries_v1")
    conn.execute("DROP INDEX IF EXISTS idx_entries_lookup")
    conn.execute("DROP INDEX IF EXISTS idx_entries_case")


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """v2 -> v3 : ajoute cases.group_prefix (préfixe du groupe distinct du préfixe des objets).
    Backfill à = prefix pour ne rien changer au comportement des cas déjà créés."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(cases)").fetchall()}
    if "group_prefix" in cols:
        return
    conn.execute("ALTER TABLE cases ADD COLUMN group_prefix TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE cases SET group_prefix = prefix WHERE group_prefix = ''")


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """v4 -> v5 : ajoute entries.device_id (pare-feu physique précis, cf. table devices).
    Entrées existantes = device_id NULL ("générique", sans device précis) ; l'unicité "actif"
    scope désormais par device (cf. idx_entries_active_unique) et plus seulement par marque — un
    IP peut être bloqué indépendamment sur deux sites différents partageant la même marque."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(entries)").fetchall()}
    if "device_id" in cols:
        return
    conn.execute("ALTER TABLE entries ADD COLUMN device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL")


@dataclass
class Case:
    id: int
    name: str
    prefix: str
    group_prefix: str
    created_at: str


def list_cases() -> list[Case]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cases ORDER BY name").fetchall()
        return [Case(**dict(r)) for r in rows]


def get_case(case_id: int) -> Case | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return Case(**dict(row)) if row else None


def create_case(name: str, prefix: str, group_prefix: str | None = None) -> Case:
    """group_prefix : préfixe du groupe, s'il doit différer du préfixe des objets (défaut : identique)."""
    now = datetime.now().isoformat(timespec="seconds")
    group_prefix = group_prefix or prefix
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cases (name, prefix, group_prefix, created_at) VALUES (?, ?, ?, ?)",
            (name, prefix, group_prefix, now),
        )
        return Case(id=cur.lastrowid, name=name, prefix=prefix, group_prefix=group_prefix, created_at=now)


def update_case(case_id: int, name: str, prefix: str, group_prefix: str | None = None) -> None:
    """Renomme un cas / change son préfixe (et éventuellement le préfixe de groupe). N'affecte pas
    les commandes déjà générées et enregistrées (elles reflètent ce qui a réellement été appliqué
    sur le pare-feu à l'époque)."""
    group_prefix = group_prefix or prefix
    with get_conn() as conn:
        conn.execute(
            "UPDATE cases SET name = ?, prefix = ?, group_prefix = ? WHERE id = ?",
            (name, prefix, group_prefix, case_id),
        )


def delete_case(case_id: int) -> None:
    """Supprime le cas et, via ON DELETE CASCADE, tout son historique d'entrées associées."""
    with get_conn() as conn:
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))


def count_entries_for_case(case_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM entries WHERE case_id = ?", (case_id,)).fetchone()
        return row["n"]


def count_history() -> dict:
    """Totaux globaux (tous cas confondus) pour les tuiles de stats de l'onglet Historique."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
        active = conn.execute("SELECT COUNT(*) AS n FROM entries WHERE unblocked_at IS NULL").fetchone()["n"]
        return {"total": total, "active": active, "archived": total - active}


def existing_normalized_for_case(case_id: int, firewall: str, device_id: int | None = None) -> set[str]:
    """Valeurs ACTIVES déjà bloquées dans CE cas pour ce pare-feu (une seule requête, pas une par
    ligne). Une entrée débloquée/archivée ne compte pas : on doit pouvoir rebloquer la même valeur.
    Scopé par device si précisé : deux sites de même marque ne se bloquent pas l'un l'autre."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT normalized FROM entries WHERE case_id = ? AND firewall = ? AND unblocked_at IS NULL "
            "AND COALESCE(device_id, -1) = COALESCE(?, -1)",
            (case_id, firewall, device_id),
        ).fetchall()
        return {row["normalized"] for row in rows}


def normalized_case_map(firewall: str, exclude_case_id: int, device_id: int | None = None) -> dict[str, str]:
    """normalized -> nom du 1er autre cas où la valeur est ACTIVEMENT déjà bloquée sur ce pare-feu
    (même device si précisé)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT e.normalized, c.name FROM entries e JOIN cases c ON c.id = e.case_id "
            "WHERE e.firewall = ? AND e.case_id != ? AND e.unblocked_at IS NULL "
            "AND COALESCE(e.device_id, -1) = COALESCE(?, -1) ORDER BY e.created_at",
            (firewall, exclude_case_id, device_id),
        ).fetchall()
        result: dict[str, str] = {}
        for row in rows:
            result.setdefault(row["normalized"], row["name"])
        return result


def add_entries(
    case_id: int, firewall: str, items: list[tuple[str, str, bool, str]], device_id: int | None = None,
) -> None:
    """Insère tout le lot (value, normalized, is_fqdn, object_name) dans une seule transaction."""
    if not items:
        return
    now = datetime.now().isoformat(timespec="seconds")
    rows = [
        (case_id, firewall, value, normalized, int(is_fqdn), object_name, device_id, now)
        for value, normalized, is_fqdn, object_name in items
    ]
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO entries (case_id, firewall, value, normalized, is_fqdn, object_name, device_id, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def backup_to(dest_path: Path) -> None:
    """Sauvegarde complète et cohérente de la base vers dest_path (API backup SQLite, pas une copie brute)."""
    with get_conn() as source:
        dest = sqlite3.connect(dest_path)
        try:
            source.backup(dest)
        finally:
            dest.close()


@dataclass
class Device:
    id: int
    site: str
    name: str
    firewall: str
    host: str
    ssh_port: int
    object_prefix: str
    group_prefix: str
    extra_options: str
    created_at: str


def list_devices() -> list[Device]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM devices ORDER BY site, name").fetchall()
        return [Device(**dict(r)) for r in rows]


def list_sites() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT site FROM devices ORDER BY site").fetchall()
        return [r["site"] for r in rows]


def get_device(device_id: int) -> Device | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return Device(**dict(row)) if row else None


def create_device(
    site: str, name: str, firewall: str, host: str, ssh_port: int = 22,
    object_prefix: str = "", group_prefix: str = "", extra_options: str = "{}",
) -> Device:
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO devices (site, name, firewall, host, ssh_port, object_prefix, group_prefix, "
            "extra_options, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (site, name, firewall, host, ssh_port, object_prefix, group_prefix, extra_options, now),
        )
        return Device(
            id=cur.lastrowid, site=site, name=name, firewall=firewall, host=host, ssh_port=ssh_port,
            object_prefix=object_prefix, group_prefix=group_prefix, extra_options=extra_options, created_at=now,
        )


def update_device(
    device_id: int, site: str, name: str, firewall: str, host: str, ssh_port: int = 22,
    object_prefix: str = "", group_prefix: str = "", extra_options: str = "{}",
) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE devices SET site = ?, name = ?, firewall = ?, host = ?, ssh_port = ?, "
            "object_prefix = ?, group_prefix = ?, extra_options = ? WHERE id = ?",
            (site, name, firewall, host, ssh_port, object_prefix, group_prefix, extra_options, device_id),
        )


def delete_device(device_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))


@dataclass
class HistoryEntry:
    entry_id: int
    case_name: str
    firewall: str
    value: str
    is_fqdn: bool
    created_at: str
    unblocked_at: str | None
    device_site: str | None
    device_name: str | None


def list_history(search: str = "", status: str = "all") -> list[HistoryEntry]:
    """status: 'all' | 'active' | 'archived'."""
    with get_conn() as conn:
        query = (
            "SELECT e.id AS entry_id, c.name AS case_name, e.firewall, e.value, e.is_fqdn, "
            "e.created_at, e.unblocked_at, d.site AS device_site, d.name AS device_name "
            "FROM entries e JOIN cases c ON c.id = e.case_id LEFT JOIN devices d ON d.id = e.device_id"
        )
        clauses: list[str] = []
        params: list = []
        if search:
            clauses.append("(c.name LIKE ? OR e.value LIKE ? OR d.site LIKE ? OR d.name LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like, like])
        if status == "active":
            clauses.append("e.unblocked_at IS NULL")
        elif status == "archived":
            clauses.append("e.unblocked_at IS NOT NULL")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY e.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [HistoryEntry(**{**dict(r), "is_fqdn": bool(r["is_fqdn"])}) for r in rows]


def archive_entries(entry_ids: list[int]) -> None:
    """Marque les entrées comme débloquées (ne les supprime pas : garde l'historique).
    Tout le lot dans une seule transaction, pour une sélection multiple dans l'UI."""
    if not entry_ids:
        return
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.executemany("UPDATE entries SET unblocked_at = ? WHERE id = ?", [(now, eid) for eid in entry_ids])


def archive_entry(entry_id: int) -> None:
    archive_entries([entry_id])


def unarchive_entries(entry_ids: list[int]) -> None:
    """Annule un archivage (remet les entrées actives) — utile en cas d'erreur de manipulation."""
    if not entry_ids:
        return
    with get_conn() as conn:
        conn.executemany("UPDATE entries SET unblocked_at = NULL WHERE id = ?", [(eid,) for eid in entry_ids])


def unarchive_entry(entry_id: int) -> None:
    unarchive_entries([entry_id])


def delete_entries(entry_ids: list[int]) -> None:
    if not entry_ids:
        return
    with get_conn() as conn:
        conn.executemany("DELETE FROM entries WHERE id = ?", [(eid,) for eid in entry_ids])


def delete_entry(entry_id: int) -> None:
    delete_entries([entry_id])
