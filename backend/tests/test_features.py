"""Career rename/delete, dashboard editing and the player list/card, on small fixtures."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from fmsa.careers import (
    CareerFileError,
    career_files,
    delete_career,
    rename_career,
    saved_queries_file,
)
from fmsa.config import MaskingSettings
from fmsa.dashboards import (
    DashboardError,
    delete_dashboard,
    load_dashboards,
    restore_dashboard,
    save_dashboard,
)
from fmsa.players import group_of, list_players, player_card, shortlist_file
from fmsa.query.session import open_career

# ---------------------------------------------------------------------------- careers


def _career(folder: Path, name: str, log_dir: Path) -> Path:
    db = folder / f"{name}.fmsa"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{name}_import001_20260101-000000.log"
    log.write_text("log", encoding="utf-8")
    conn = sqlite3.connect(db)
    conn.executescript(
        f"""
        PRAGMA journal_mode=WAL;
        CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO _meta VALUES ('career_name', '{name}');
        CREATE TABLE _imports (import_id INTEGER PRIMARY KEY, log_file TEXT);
        INSERT INTO _imports VALUES (1, '{log}');
        """
    )
    conn.commit()
    conn.close()
    return db


def test_rename_moves_every_file(tmp_path: Path) -> None:
    data, logs = tmp_path / "data", tmp_path / "data" / "logs" / "imports"
    (data / "careers").mkdir(parents=True)
    db = _career(data / "careers", "Old", logs)
    queries = saved_queries_file(data, db)
    queries.parent.mkdir(parents=True)
    queries.write_text("[]", encoding="utf-8")
    shortlist = shortlist_file(data, db)
    shortlist.parent.mkdir(parents=True)
    shortlist.write_text("[]", encoding="utf-8")

    target = rename_career(db, "New name", data, logs)
    assert target.name == "New name.fmsa" and target.is_file() and not db.exists()
    assert saved_queries_file(data, target).is_file() and not queries.exists()
    assert shortlist_file(data, target).is_file() and not shortlist.exists()
    assert [p.name for p in logs.iterdir()] == ["New name_import001_20260101-000000.log"]
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT value FROM _meta WHERE key = 'career_name'").fetchone() == (
        "New name",
    )
    assert (
        conn.execute("SELECT log_file FROM _imports")
        .fetchone()[0]
        .endswith("New name_import001_20260101-000000.log")
    )
    conn.close()


def test_rename_refuses_existing_name(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    a = _career(tmp_path, "A", logs)
    _career(tmp_path, "B", logs)
    with pytest.raises(CareerFileError):
        rename_career(a, "B", tmp_path, logs)


def test_delete_removes_every_file(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    db = _career(tmp_path, "Gone", logs)
    queries = saved_queries_file(tmp_path, db)
    queries.parent.mkdir(parents=True)
    queries.write_text("[]", encoding="utf-8")
    files = career_files(db, tmp_path, logs)
    assert db in files and queries in files
    deleted = delete_career(db, tmp_path, logs)
    assert str(db) in deleted
    assert not db.exists() and not queries.exists() and not list(logs.iterdir())


# ---------------------------------------------------------------------------- dashboards


def _dash(dashboard_id: str) -> dict:
    return {
        "id": dashboard_id,
        "title": {"it": "T", "en": "T"},
        "description": {"it": "", "en": ""},
        "params": [],
        "widgets": [{"id": "w", "type": "table", "sql": "SELECT 1"}],
    }


def test_dashboard_save_delete_restore(tmp_path: Path) -> None:
    user = tmp_path / "dashboards"
    saved = save_dashboard(user, _dash("mine"))
    assert saved["source"] == "user" and not saved["builtin"]
    assert "mine" in load_dashboards(user)

    # a user copy of a built-in one replaces it, delete hides it, restore brings it back
    builtin = load_dashboards(None)["squad"]
    edited = {**builtin, "title": {"it": "Mia rosa", "en": "My squad"}}
    assert save_dashboard(user, edited)["title"]["it"] == "Mia rosa"
    delete_dashboard(user, "squad")
    assert "squad" not in load_dashboards(user)
    restore_dashboard(user, "squad")
    restored = load_dashboards(user)["squad"]
    assert restored["source"] == "builtin" and restored["title"]["it"] != "Mia rosa"

    delete_dashboard(user, "mine")
    assert "mine" not in load_dashboards(user)
    assert not (user / "mine.json").exists()

    # renaming a user dashboard removes the old file
    save_dashboard(user, _dash("first"))
    save_dashboard(user, _dash("second"), old_id="first")
    assert {"first", "second"} & set(load_dashboards(user)) == {"second"}


def test_dashboard_validation(tmp_path: Path) -> None:
    with pytest.raises(DashboardError):
        save_dashboard(tmp_path, _dash("bad id"))
    twice = _dash("twice")
    twice["widgets"] = twice["widgets"] * 2
    with pytest.raises(DashboardError):
        save_dashboard(tmp_path, twice)


# ---------------------------------------------------------------------------- players

ATTRS = ("finishing", "pace", "consistency")


@pytest.fixture
def career(tmp_path: Path) -> Path:
    db = tmp_path / "p.fmsa"
    conn = sqlite3.connect(db)
    attr_cols = ", ".join(f"attributes_{a}" for a in ATTRS)
    conn.executescript(
        f"""
        CREATE TABLE _columns (table_name, column_name, sql_type, source_path, field_status,
                               position);
        INSERT INTO _columns VALUES
            ('players', 'ability_potential', '', 'players.ability.potential', '', 0),
            ('players', 'attributes_consistency', '', 'players.attributes.consistency', '', 1);
        CREATE TABLE players (uid, birth_date, name, age, natural_positions,
            accomplished_positions, ability_current, ability_potential, club_name, club_uid,
            transfer_value, contract_wage, contract_end, traits, {attr_cols});
        CREATE TABLE player_season_stats (player_uid, kind, starts, substitute_appearances,
            minutes, rated_appearances, average_rating, goals, assists);
        CREATE TABLE contracts (_import_id, contracts_idx, player_uid, club_name, wage, "end");
        CREATE TABLE contracts_clauses (_import_id, contracts_idx, clauses_idx, kind,
            parameter, value);
        """
    )
    players = [
        (1, "2000-01-01", "Ala Uno", 25, '["AML"]', 150, 170, 10, 18, 5),
        (2, "2001-01-01", "Ala Due", 24, '["AMR","MR"]', 140, 150, 12, 12, 9),
        (3, "1999-01-01", "Punta", 26, '["STC"]', 160, 160, 18, 14, 9),
    ]
    for uid, born, name, age, pos, ca, pa, fin, pace, cons in players:
        conn.execute(
            f"INSERT INTO players (uid, birth_date, name, age, natural_positions, "
            f"accomplished_positions, ability_current, ability_potential, club_name, club_uid, "
            f"transfer_value, contract_wage, contract_end, traits, {attr_cols}) "
            "VALUES (?, ?, ?, ?, ?, '[]', ?, ?, 'FC', 7, 1000, 10, '2030-06-30', "
            '\'["unknown","runs_with_ball_often"]\', ?, ?, ?)',
            (uid, born, name, age, pos, ca, pa, fin, pace, cons),
        )
        conn.execute(
            "INSERT INTO player_season_stats VALUES (?, 'league', 30, 2, 2700, 32, 7.0, ?, 1)",
            (uid, uid * 3),
        )
    conn.execute("INSERT INTO contracts VALUES (1, 0, 1, 'FC', 10, '2030-06-30')")
    conn.execute("INSERT INTO contracts_clauses VALUES (1, 0, 0, 'appearance_fee', NULL, 50)")
    conn.commit()
    conn.close()
    return db


def test_group_of() -> None:
    assert group_of(["AML", "STC"]) == "wingers"
    assert group_of(["STC"]) == "strikers"
    assert group_of([]) is None


def test_list_players_masks_and_sorts(career: Path) -> None:
    with open_career(career, MaskingSettings(potential_ability=True)) as s:
        page = list_players(s, sort="ca", desc=True)
        assert [r["name"] for r in page["rows"]] == ["Punta", "Ala Uno", "Ala Due"]
        assert all(r["pa"] is None for r in page["rows"]) and page["masked"] == ["pa"]
        assert page["rows"][0]["goals"] == 9
        wingers = list_players(s, group="wingers", sort="name", desc=False)
        assert [r["name"] for r in wingers["rows"]] == ["Ala Due", "Ala Uno"]
        assert list_players(s, search="punt")["total"] == 1
        only = list_players(s, only=[(2, "2001-01-01")])
        assert [r["name"] for r in only["rows"]] == ["Ala Due"]


def test_player_card_ranks_against_role(career: Path) -> None:
    with open_career(career, MaskingSettings(potential_ability=False, hidden_attributes=True)) as s:
        card = player_card(s, 1, "2000-01-01")
    assert card["group"] == "wingers"
    technical = {a["key"]: a for a in card["attributes"]["technical"]}
    physical = {a["key"]: a for a in card["attributes"]["physical"]}
    # against the two wingers only: finishing 10 < 12, pace 18 > 12
    assert technical["finishing"]["rank"] == 25
    assert physical["pace"]["rank"] == 75
    hidden = {a["key"]: a for a in card["attributes"]["hidden"]}
    assert hidden["consistency"]["hidden"] and hidden["consistency"]["value"] is None
    assert card["traits"] == ["runs_with_ball_often"]
    assert card["contract"]["clauses"] == [
        {"kind": "appearance_fee", "parameter": None, "value": 50}
    ]
    assert card["stats"]["kind"] == "league"
    goals = next(r for r in card["stats"]["rows"] if r["key"] == "goals")
    assert goals["total"] == 3 and goals["per90"] == pytest.approx(0.1)


def test_shortlist_file_is_per_career(tmp_path: Path) -> None:
    a = shortlist_file(tmp_path, tmp_path / "a.fmsa")
    b = shortlist_file(tmp_path, tmp_path / "b.fmsa")
    assert a != b and a.parent.name == "shortlists"
    json.dumps({})  # keep json import used
