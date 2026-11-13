"""Read-only guarantees and masking of spoiler columns."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fmsa.config import MaskingSettings
from fmsa.query.session import QueryError, ReadOnlySession, open_career


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "career.fmsa"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE _columns (table_name, column_name, sql_type, source_path, field_status,
                               position);
        INSERT INTO _columns VALUES
          ('players', 'name', 'TEXT', 'name', '', 0),
          ('players', 'ability_current', 'INTEGER', 'ability.current', '', 1),
          ('players', 'ability_potential', 'INTEGER', 'ability.potential', '', 2),
          ('players', 'attributes_consistency', 'INTEGER', 'attributes.consistency', '', 3),
          ('players', 'personality_ambition', 'INTEGER', 'personality.ambition', '', 4),
          ('staff', 'ability_potential', 'INTEGER', 'ability.potential', '', 0);
        CREATE TABLE players_all (_rid INTEGER PRIMARY KEY, _key, _hash, _valid_to, uid, name,
            club_uid, ability_current, ability_potential, attributes_consistency,
            personality_ambition);
        INSERT INTO players_all VALUES
            (1, 11, 99, NULL, 1, 'Alpha', 10, 120, 190, 15, 18),
            (2, 12, 98, NULL, 2, 'Beta', 10, 140, 145, 9, 7);
        CREATE VIEW players AS SELECT * FROM players_all WHERE _valid_to IS NULL;
        CREATE TABLE staff_all (_rid INTEGER PRIMARY KEY, name, ability_potential);
        INSERT INTO staff_all VALUES (1, 'Coach', 160);
        CREATE VIEW staff AS SELECT * FROM staff_all;
        CREATE TABLE clubs_all (uid, name);
        INSERT INTO clubs_all VALUES (10, 'Club');
        """
    )
    conn.commit()
    conn.close()
    return path


def session(db: Path, **mask: bool) -> ReadOnlySession:
    return open_career(db, MaskingSettings(**mask))


# ---------------------------------------------------------------- read-only


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO clubs_all VALUES (11, 'x')",
        "UPDATE clubs_all SET name = 'x'",
        "DELETE FROM clubs_all",
        "DROP TABLE clubs_all",
        "CREATE TABLE t (a)",
        "CREATE TEMP TABLE t (a)",
        "CREATE VIEW v AS SELECT 1",
        "ALTER TABLE clubs_all ADD COLUMN x",
        "ATTACH DATABASE ':memory:' AS other",
        "PRAGMA query_only = OFF",
        "PRAGMA writable_schema = ON",
        "BEGIN",
        "VACUUM",
        "REPLACE INTO clubs_all VALUES (1, 'x')",
        "WITH x AS (SELECT 1) DELETE FROM clubs_all",
        "SELECT load_extension('evil')",
    ],
)
def test_writes_and_side_effects_refused(db: Path, sql: str) -> None:
    with session(db) as s, pytest.raises(QueryError):
        s.query(sql)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*), max(name) FROM clubs_all").fetchone() == (1, "Club")
    assert conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 6


def test_multiple_statements_refused(db: Path) -> None:
    with session(db) as s, pytest.raises(QueryError):
        s.query("SELECT 1; DELETE FROM clubs_all")


def test_reads_allowed(db: Path) -> None:
    with session(db, potential_ability=False) as s:
        r = s.query(
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 3) "
            "SELECT p.name, c.name AS club, (SELECT count(*) FROM n) AS k "
            "FROM players p JOIN clubs_all c ON c.uid = p.club_uid ORDER BY p.name;"
        )
    assert r.columns == ["name", "club", "k"]
    assert r.rows == [["Alpha", "Club", 3], ["Beta", "Club", 3]]


def test_row_limit_and_timeout(db: Path) -> None:
    with session(db) as s:
        r = s.query("SELECT * FROM players", limit=1)
        assert r.truncated and len(r.rows) == 1
    slow = ReadOnlySession(db, timeout_s=0.2)
    with pytest.raises(QueryError, match="stopped"):
        slow.query(
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT count(*) FROM n"
        )
    slow.close()


# ---------------------------------------------------------------- masking


def test_potential_masked_by_default(db: Path) -> None:
    with open_career(db, MaskingSettings()) as s:
        r = s.query("SELECT name, ability_current, ability_potential FROM players ORDER BY uid")
        assert r.rows == [["Alpha", 120, None], ["Beta", 140, None]]
        assert r.masked == ["ability_potential"]
        assert s.query("SELECT * FROM players_all").rows[0][8] is None
        assert s.query("SELECT ability_potential FROM staff").rows == [[None]]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM players WHERE ability_potential > 180",
        "SELECT name FROM players WHERE ability_potential IS NOT NULL",
        "SELECT name FROM players ORDER BY ability_potential DESC LIMIT 1",
        "SELECT max(ability_potential) FROM players_all",
        "SELECT name FROM players p WHERE EXISTS "
        "(SELECT 1 FROM players_all a WHERE a.uid = p.uid AND a.ability_potential > 150)",
        "SELECT ability_potential - ability_current FROM players",
        "WITH x AS (SELECT ability_potential AS hidden FROM players) SELECT hidden FROM x",
        "SELECT _hash FROM players_all",
    ],
)
def test_masked_values_never_leak(db: Path, sql: str) -> None:
    with open_career(db, MaskingSettings()) as s:
        rows = s.query(sql).rows
    flat = [v for row in rows for v in row]
    assert 190 not in flat and 145 not in flat and 99 not in flat
    # filters on a hidden column cannot single anyone out
    assert rows in ([], [[None]], [[None], [None]], [["Alpha"]], [["Beta"]]) or all(
        v is None for v in flat
    )
    if "WHERE ability_potential" in sql:
        assert rows == []


def test_presets(db: Path) -> None:
    sql = (
        "SELECT ability_current, ability_potential, attributes_consistency, "
        "personality_ambition FROM players WHERE uid = 1"
    )
    with open_career(db, MaskingSettings(potential_ability=False)) as s:
        assert s.query(sql).rows == [[120, 190, 15, 18]]
    everything = MaskingSettings(
        potential_ability=True, current_ability=True, hidden_attributes=True, personality=True
    )
    with open_career(db, everything) as s:
        assert s.query(sql).rows == [[None, None, None, None]]


def test_extra_columns(db: Path) -> None:
    m = MaskingSettings(potential_ability=False, extra_columns=["players.name"])
    with open_career(db, m) as s:
        assert s.query("SELECT name, uid FROM players WHERE uid = 1").rows == [[None, 1]]
        assert s.query("SELECT name FROM clubs_all").rows == [["Club"]]


def test_query_and_schema_api(db: Path, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from fmsa.config import SettingsStore
    from fmsa.paths import PORTABLE_FLAG, AppPaths
    from fmsa.server import TOKEN_HEADER, create_app

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / PORTABLE_FLAG).touch()
    paths = AppPaths.resolve(app_dir=app_dir, bundle_dir=tmp_path / "bundle")
    paths.ensure()
    store = SettingsStore(paths)
    client = TestClient(create_app(paths, store, "t"), base_url="http://127.0.0.1")
    h = {TOKEN_HEADER: "t"}
    assert client.post("/api/query", json={"sql": "SELECT 1"}, headers=h).status_code == 409

    store.save(store.get().model_copy(update={"last_career": str(db)}))
    r = client.post("/api/query", json={"sql": "SELECT name, ability_potential FROM players"},
                    headers=h).json()  # fmt: skip
    assert r["rows"] == [["Alpha", None], ["Beta", None]]
    assert r["masked"] == ["ability_potential"]
    bad = client.post("/api/query", json={"sql": "DELETE FROM players_all"}, headers=h)
    assert bad.status_code == 400 and "read-only" in bad.json()["detail"]

    objects = {o["name"]: o for o in client.get("/api/schema", headers=h).json()["objects"]}
    cols = {c["name"]: c for c in objects["players"]["columns"]}
    assert cols["ability_potential"]["masked"] and not cols["ability_current"]["masked"]
    assert cols["_hash"]["masked"] and cols["_hash"]["internal"]


def test_masked_column_keeps_its_name_in_joins(db: Path) -> None:
    with open_career(db, MaskingSettings()) as s:
        r = s.query('SELECT t1."ability_potential", t1.name FROM players AS t1')
    assert r.columns == ["ability_potential", "name"]
    assert r.masked == ["ability_potential"]


def test_rules_match_the_same_field_under_other_parents() -> None:
    from fmsa.query.masking import MaskRules

    rules = MaskRules.from_settings(MaskingSettings(hidden_attributes=True, personality=True))
    assert rules.matches("attributes.consistency")
    assert rules.matches("raw_attributes.consistency")
    assert rules.matches("personality.ambition") and rules.matches("staff.personality.ambition")
    assert not rules.matches("attributes.finishing")
