"""Dashboard definitions, API and export."""

from __future__ import annotations

import io
import json
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fmsa.config import MaskingSettings, SettingsStore
from fmsa.dashboards import BUILTIN_DIR, load_dashboards, param_options, run_dashboard
from fmsa.paths import PORTABLE_FLAG, AppPaths
from fmsa.query.session import open_career
from fmsa.server import TOKEN_HEADER, create_app

H = {TOKEN_HEADER: "t"}


def test_builtin_definitions_are_valid() -> None:
    dashboards = load_dashboards()
    assert len(dashboards) == len(list(BUILTIN_DIR.glob("*.json"))) == 10
    for d in dashboards.values():
        assert d["title"]["it"] and d["title"]["en"]
        ids = [w["id"] for w in d["widgets"]]
        assert len(ids) == len(set(ids)), d["id"]
        for w in d["widgets"]:
            assert w["title"]["it"] and w["title"]["en"]
            # every named parameter used by the SQL is one the dashboard declares
            for p in ("club", "competition", "season"):
                if f":{p}" in w["sql"]:
                    assert p in d["params"], (d["id"], w["id"], p)


def test_user_dashboards_add_and_override(tmp_path: Path) -> None:
    (tmp_path / "mine.json").write_text(
        json.dumps({"id": "mine", "title": {"it": "Mia", "en": "Mine"}, "widgets": [
            {"id": "a", "type": "kpi", "sql": "SELECT 1 AS value", "title": {"it": "x"}}]}),
        encoding="utf-8",
    )  # fmt: skip
    (tmp_path / "squad.json").write_text(
        json.dumps({"id": "squad", "title": {"it": "Mia rosa"}, "order": 0, "widgets": []}),
        encoding="utf-8",
    )
    (tmp_path / "broken.json").write_text("{nope", encoding="utf-8")
    (tmp_path / "bad.json").write_text(json.dumps({"id": "bad", "widgets": [{"id": "w"}]}))
    d = load_dashboards(tmp_path)
    assert d["mine"]["source"] == "user"
    assert d["squad"]["title"]["it"] == "Mia rosa"
    assert "bad" not in d and "broken" not in d
    assert next(iter(d)) == "squad"  # order 0 first


@pytest.fixture
def career(tmp_path: Path) -> Path:
    db = tmp_path / "c.fmsa"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE _imports (import_id INTEGER PRIMARY KEY, game_date TEXT, status TEXT);
        INSERT INTO _imports VALUES (1, '2030-06-15', 'ok');
        CREATE TABLE _columns (table_name, column_name, sql_type, source_path, field_status,
                               position);
        INSERT INTO _columns VALUES ('players', 'ability_potential', 'INTEGER',
                                    'ability.potential', '', 0);
        CREATE TABLE clubs (uid, name, reputation, gender_label);
        INSERT INTO clubs VALUES (1, 'Women FC', 9000, 'WOMEN'), (2, 'Men FC', 5000, 'MEN');
        CREATE TABLE players (uid, name, age, club_uid, ability_current, ability_potential,
                              transfer_value, natural_positions, birth_date);
        INSERT INTO players VALUES (10, 'A', 20, 2, 120, 170, 1000, '["ST"]', '2010-01-01'),
                                   (11, 'B', 30, 2, 140, 150, 3000, '["GK"]', '1999-01-01');
        CREATE TABLE contracts (player_uid, club_uid, wage, "end", squad_status_label,
                                player_name);
        INSERT INTO contracts VALUES (10, 2, 500, '2031-01-01', 'KEY', 'A');
        CREATE TABLE player_season_history (season_year, kind, player_uid);
        INSERT INTO player_season_history VALUES (2030, 'league', 10);
        WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 20)
        INSERT INTO player_season_history SELECT 2029, 'league', i FROM n;
        """
    )
    conn.commit()
    conn.close()
    return db


def test_params_and_partial_failures(career: Path) -> None:
    with open_career(career, MaskingSettings()) as s:
        p = param_options(s)
        assert p["today"] == "2030-06-15"
        assert p["club"]["options"][0] == {"value": 2, "label": "Men FC"}
        assert p["club"]["options"][1]["label"] == "Women FC ♀"
        assert p["season"]["default"] == 2029  # 2030 has barely started
        assert p["competition"]["options"] == []  # no league tables in this fixture
        res = run_dashboard(s, load_dashboards()["squad"], {"club": 2}, p["today"])
    assert res["players"]["rows"] == [[2]]
    assert res["list"]["masked"] == ["ability_potential"]
    assert all(r[4] is None for r in res["list"]["rows"])  # potential hidden


def test_api_and_zip_export(career: Path, tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / PORTABLE_FLAG).touch()
    paths = AppPaths.resolve(app_dir=app_dir, bundle_dir=tmp_path / "bundle")
    paths.ensure()
    store = SettingsStore(paths)
    store.save(store.get().model_copy(update={"last_career": str(career)}))
    client = TestClient(create_app(paths, store, "t"), base_url="http://127.0.0.1")

    assert len(client.get("/api/dashboards", headers=H).json()) == 10
    data = client.post("/api/dashboards/contracts/data", json={"params": {"club": 2}},
                       headers=H).json()["widgets"]  # fmt: skip
    assert data["expiring"]["rows"] == [[1]]  # uses :today
    # widgets whose tables this fixture lacks fail alone
    finances = client.post("/api/dashboards/finances/data", json={"params": {"club": 2}},
                           headers=H).json()["widgets"]  # fmt: skip
    assert all("error" in w for w in finances.values())

    r = client.post("/api/dashboards/squad/export",
                    json={"params": {"club": 2}, "format": "csv_excel"}, headers=H)  # fmt: skip
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "parameters.json" in names and "07_list.csv" in names
    text = z.read("07_list.csv").decode("utf-8-sig")
    assert text.splitlines()[0].startswith("name;age;positions")
    assert client.get("/api/dashboards/nope", headers=H).status_code == 404


@pytest.mark.skipif(not os.environ.get("FMSA_TEST_CAREER"), reason="FMSA_TEST_CAREER not set")
def test_every_dashboard_runs_on_a_real_career() -> None:
    db = Path(os.environ["FMSA_TEST_CAREER"])
    with open_career(db, MaskingSettings()) as s:
        p = param_options(s)
        params = {k: p[k]["default"] for k in ("club", "competition", "season")}
        for d in load_dashboards().values():
            res = run_dashboard(s, d, params, p["today"])
            errors = {k: v["error"] for k, v in res.items() if "error" in v}
            assert not errors, (d["id"], errors)
