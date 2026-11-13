"""Browse (grid paging/filters), export, saved queries and relations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fmsa.config import SettingsStore
from fmsa.paths import PORTABLE_FLAG, AppPaths
from fmsa.server import TOKEN_HEADER, create_app

H = {TOKEN_HEADER: "t"}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "career.fmsa"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE _tables (table_name, base_table, reader, kind, parent_table, record_type,
                              key_columns);
        INSERT INTO _tables VALUES ('players', 'players_history', 'players', 'entity', NULL,
                                    'Player', '[]'),
                                   ('Club', 'Club_history', 'clubs', 'entity', NULL, 'Club', '[]'),
                                   ('Team', 'Team_history', 'clubs', 'child', 'Club', 'Team',
                                    NULL);
        CREATE TABLE _columns (table_name, column_name, sql_type, source_path, field_status,
                               position);
        INSERT INTO _columns VALUES ('players', 'ability_potential', 'INTEGER',
                                     'Player.ability.potential', '', 0);
        CREATE TABLE players (_rid INTEGER PRIMARY KEY, uid INTEGER, name TEXT,
            birth_date TEXT, club_uid INTEGER, ability_potential INTEGER);
        INSERT INTO players VALUES
            (1, 1, 'Mario Rossi', '2000-01-10', 10, 180),
            (2, 2, 'Luca Bianchi', '1995-05-05', 10, 150),
            (3, 3, 'Paolo 100%_Neri', '2004-03-03', 20, 170);
        CREATE TABLE players_history AS SELECT *, NULL AS _valid_to FROM players WHERE 0;
        CREATE VIEW players_all AS SELECT *, NULL AS _valid_to FROM players;
        CREATE TABLE Club (_rid INTEGER PRIMARY KEY, uid INTEGER, name TEXT);
        INSERT INTO Club VALUES (1, 10, 'Juventus'), (2, 20, 'Torino');
        CREATE TABLE Club_history AS SELECT * FROM Club WHERE 0;
        CREATE VIEW Club_all AS SELECT * FROM Club;
        CREATE TABLE Team (_rid INTEGER PRIMARY KEY, _parent_table, _parent_rid, team_id);
        CREATE TABLE Team_history AS SELECT * FROM Team WHERE 0;
        CREATE VIEW Team_all AS SELECT * FROM Team;
        """
    )
    conn.commit()
    conn.close()
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / PORTABLE_FLAG).touch()
    paths = AppPaths.resolve(app_dir=app_dir, bundle_dir=tmp_path / "bundle")
    paths.ensure()
    store = SettingsStore(paths)
    store.save(store.get().model_copy(update={"last_career": str(db)}))
    return TestClient(create_app(paths, store, "t"), base_url="http://127.0.0.1")


def browse(client: TestClient, **body: object) -> dict:  # type: ignore[type-arg]
    r = client.post("/api/browse", json={"table": "players", **body}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_browse_paging_sort_and_count(client: TestClient) -> None:
    page = browse(client, columns=["name"], sort_model=[{"colId": "name", "sort": "desc"}],
                  start=1, end=2)  # fmt: skip
    assert page["rows"] == [["Mario Rossi"]]
    assert page["total"] == 3


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ({"name": {"filterType": "text", "type": "contains", "filter": "ROSSI"}}, ["Mario Rossi"]),
        ({"name": {"filterType": "text", "type": "startsWith", "filter": "paolo 100%_"}},
         ["Paolo 100%_Neri"]),
        ({"name": {"filterType": "text", "type": "startsWith", "filter": "%"}}, []),
        ({"club_uid": {"filterType": "number", "type": "equals", "filter": 10}},
         ["Mario Rossi", "Luca Bianchi"]),
        ({"birth_date": {"filterType": "date", "type": "inRange",
                         "dateFrom": "1999-01-01 00:00:00", "dateTo": "2001-01-01 00:00:00"}},
         ["Mario Rossi"]),
        ({"name": {"filterType": "text", "operator": "OR", "conditions": [
            {"filterType": "text", "type": "equals", "filter": "luca bianchi"},
            {"filterType": "text", "type": "endsWith", "filter": "neri"}]}},
         ["Luca Bianchi", "Paolo 100%_Neri"]),
        # a hidden column reads as NULL: filtering on it finds nobody
        ({"ability_potential": {"filterType": "number", "type": "greaterThan", "filter": 160}},
         []),
    ],
)  # fmt: skip
def test_browse_filters(client: TestClient, model: dict, expected: list[str]) -> None:  # type: ignore[type-arg]
    page = browse(client, columns=["name"], filter_model=model,
                  sort_model=[{"colId": "uid", "sort": "asc"}])  # fmt: skip
    assert [r[0] for r in page["rows"]] == expected


def test_browse_rejects_unknown_identifiers(client: TestClient) -> None:
    bad = {"table": "players", "sort_model": [{"colId": "name; DROP TABLE x", "sort": "asc"}]}
    assert client.post("/api/browse", json=bad, headers=H).status_code == 400
    assert client.post("/api/browse", json={"table": "nope"}, headers=H).status_code == 404


def test_export_to_file_and_stream(client: TestClient, tmp_path: Path) -> None:
    target = tmp_path / "out.csv"
    body = {"format": "csv_excel", "sql": "SELECT name, ability_potential FROM players "
            "ORDER BY uid", "path": str(target)}  # fmt: skip
    r = client.post("/api/export", json=body, headers=H).json()
    assert r["rows"] == 3
    text = target.read_bytes().decode("utf-8-sig")
    assert text.splitlines()[:2] == ["name;ability_potential", "Mario Rossi;"]

    browse_body = {"table": "players", "columns": ["uid", "name"],
                   "sort_model": [{"colId": "uid", "sort": "asc"}]}  # fmt: skip
    r = client.post("/api/export", json={"format": "json", "browse": browse_body}, headers=H)
    assert json.loads(r.content)[0] == {"uid": 1, "name": "Mario Rossi"}


def test_saved_queries_roundtrip(client: TestClient) -> None:
    assert client.get("/api/saved-queries", headers=H).json() == []
    items = [{"name": "Rosa", "sql": "SELECT * FROM players", "model": None}]
    assert client.put("/api/saved-queries", json=items, headers=H).status_code == 200
    assert client.get("/api/saved-queries", headers=H).json() == items


def test_relations_in_schema(client: TestClient) -> None:
    rel = client.get("/api/schema", headers=H).json()["relations"]
    pairs = {(r["from_table"], r["from_column"], r["to_table"], r["to_column"]) for r in rel}
    assert ("players", "club_uid", "Club", "uid") in pairs
    assert ("players_all", "club_uid", "Club", "uid") in pairs
    assert ("Team", "_parent_rid", "Club", "_rid") in pairs
    assert ("Team_all", "_parent_rid", "Club_all", "_rid") in pairs
    assert ("Team_history", "_parent_rid", "Club_history", "_rid") in pairs
