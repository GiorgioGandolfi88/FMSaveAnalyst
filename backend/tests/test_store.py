"""Merge semantics of the career database store, with small synthetic record types."""

from __future__ import annotations

import datetime as dt
import enum
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

import fmsave
import fmsave.export
import pytest

from fmsa.db import open_writer
from fmsa.ingest.readers import CATEGORIES, Kind, ReaderSpec
from fmsa.ingest.schema import build_layout, child_fields
from fmsa.ingest.store import TableWriter


class Foot(enum.IntEnum):
    LEFT = 1
    RIGHT = 2


@dataclass(frozen=True)
class Ability:
    current: int
    potential: int | None


@dataclass(frozen=True)
class Trait:
    code: int
    name: str


@dataclass(frozen=True)
class Person:
    UNKNOWN_KEYS = ("x",)

    uid: int
    name: str
    birth_date: dt.date
    ability: Ability
    foot: fmsave.CodedValue[Foot] | None
    positions: tuple[str, ...]
    traits: tuple[Trait, ...]
    unknown: Mapping[str, int]


@dataclass(frozen=True)
class Match:
    date: dt.date
    home: int
    away: int
    home_goals: int | None
    away_goals: int | None


PEOPLE = ReaderSpec("people", Kind.ENTITY, ("uid", "birth_date"))
MATCHES = ReaderSpec("matches", Kind.EVENT, ("date", "home", "away"))


def person(uid: int, ca: int, born: str = "2000-01-01", traits: int = 1, name: str = "") -> Person:
    return Person(
        uid=uid,
        name=name or f"P{uid}",
        birth_date=dt.date.fromisoformat(born),
        ability=Ability(ca, 180),
        foot=fmsave.CodedValue(Foot.LEFT, 1),
        positions=("ST", "AMC"),
        traits=tuple(Trait(i, f"t{i}") for i in range(traits)),
        unknown={"x": 1},
    )


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:  # type: ignore[no-untyped-def]
    return open_writer(tmp_path / "t.fmsa")


def test_layout_matches_normalize() -> None:
    layout = build_layout(Person, "people")
    assert layout.table == "people"
    assert layout.keys == ["people_idx"]
    # the list of sub-records is a child table, the group stays flattened in the parent
    expected = [c for c in fmsave.export.column_names(Person) if c != "traits"]
    assert layout.column_names == expected
    assert "ability_current" in layout.column_names
    assert [(c.table, c.field_name, c.keys) for c in layout.children] == [
        ("people_traits", "traits", ["people_idx", "traits_idx"]),
    ]


def test_entity_versions_move_to_history(conn: sqlite3.Connection) -> None:
    w = TableWriter(conn, PEOPLE, Person)
    s = w.merge([person(1, 100), person(2, 90, traits=2)], import_id=1)
    assert (s.rows, s.inserted) == (2, 2)
    # player 1 improves, player 2 leaves the save, player 3 arrives
    w = TableWriter(conn, PEOPLE, Person)
    s = w.merge([person(1, 110), person(3, 80)], import_id=2)
    w.ensure_views()
    assert (s.inserted, s.updated, s.unchanged, s.closed) == (1, 1, 0, 1)
    current = conn.execute(
        "SELECT uid, ability_current, _import_id, people_idx FROM people ORDER BY uid"
    )
    assert current.fetchall() == [(1, 110, 2, 0), (3, 80, 2, 1)]
    history = conn.execute(
        "SELECT uid, ability_current, _import_id, _valid_to FROM people_history ORDER BY uid"
    )
    assert history.fetchall() == [(1, 100, 1, 2), (2, 90, 1, 2)]
    assert conn.execute("SELECT count(*) FROM people_all").fetchone()[0] == 4
    # child rows follow their parent
    assert conn.execute("SELECT count(*) FROM people_traits").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM people_traits_history").fetchone()[0] == 3
    assert conn.execute("SELECT count(*) FROM people_traits_all").fetchone()[0] == 5
    rows = conn.execute(
        "SELECT p.uid, t.traits_idx, t.name FROM people_traits t JOIN people p "
        "ON p._import_id = t._import_id AND p.people_idx = t.people_idx ORDER BY p.uid"
    ).fetchall()
    assert rows == [(1, 0, "t0"), (3, 0, "t0")]
    assert conn.execute(
        "SELECT positions, foot, foot_code, unknown_x FROM people WHERE uid = 1"
    ).fetchone() == ('["ST","AMC"]', "left", 1, 1)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(people)")]
    assert "traits" not in cols


def test_unchanged_rows_keep_their_children(conn: sqlite3.Connection) -> None:
    TableWriter(conn, PEOPLE, Person).merge([person(1, 100), person(2, 90, traits=3)], 1)
    s = TableWriter(conn, PEOPLE, Person).merge([person(5, 70), person(2, 90, traits=3)], 2)
    assert (s.unchanged, s.inserted, s.closed) == (1, 1, 1)
    rows = conn.execute(
        "SELECT p.uid, p._import_id, count(t._rid) FROM people p LEFT JOIN people_traits t "
        "ON p._import_id = t._import_id AND p.people_idx = t.people_idx "
        "GROUP BY p._rid ORDER BY p.uid"
    ).fetchall()
    assert rows == [(2, 1, 3), (5, 2, 1)]


def test_child_change_creates_new_version(conn: sqlite3.Connection) -> None:
    TableWriter(conn, PEOPLE, Person).merge([person(1, 100, traits=1)], import_id=1)
    s = TableWriter(conn, PEOPLE, Person).merge([person(1, 100, traits=2)], import_id=2)
    assert s.updated == 1
    assert conn.execute("SELECT count(*) FROM people_traits").fetchone()[0] == 2


def test_events_accumulate_and_update(conn: sqlite3.Connection) -> None:
    first = [Match(dt.date(2026, 1, 1), 1, 2, 1, 0), Match(dt.date(2026, 2, 1), 2, 1, None, None)]
    TableWriter(conn, MATCHES, Match).merge(first, import_id=1)
    second = [Match(dt.date(2026, 2, 1), 2, 1, 2, 2), Match(dt.date(2026, 3, 1), 1, 3, None, None)]
    w = TableWriter(conn, MATCHES, Match)
    s = w.merge(second, import_id=2)
    assert w.ensure_views() == []  # events keep everything in the table itself
    assert (s.inserted, s.updated, s.unchanged) == (1, 1, 0)
    rows = conn.execute(
        "SELECT date, home_goals, _first_seen, _last_seen, _import_id FROM matches ORDER BY date"
    ).fetchall()
    assert rows == [
        ("2026-01-01", 1, 1, 1, 1),
        ("2026-02-01", 2, 1, 2, 2),
        ("2026-03-01", None, 2, 2, 2),
    ]


def test_identical_duplicates_are_kept(conn: sqlite3.Connection) -> None:
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    spec = ReaderSpec("dups", Kind.EVENT)
    TableWriter(conn, spec, Match).merge([m, m], import_id=1)
    s = TableWriter(conn, spec, Match).merge([m, m], import_id=2)
    assert s.unchanged == 2
    assert conn.execute("SELECT count(*) FROM dups").fetchone()[0] == 2


def test_snapshot_keeps_last_copy_and_history(conn: sqlite3.Connection) -> None:
    spec = ReaderSpec("snap", Kind.SNAPSHOT)
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    TableWriter(conn, spec, Match).merge([m], import_id=1)
    w = TableWriter(conn, spec, Match)
    w.merge([m, m], import_id=2)
    w.ensure_views()
    assert conn.execute("SELECT _import_id, snap_idx FROM snap").fetchall() == [(2, 0), (2, 1)]
    assert conn.execute("SELECT _import_id, _valid_to FROM snap_history").fetchall() == [(1, 2)]
    assert conn.execute("SELECT count(*) FROM snap_all").fetchone()[0] == 3


def test_new_column_is_added(conn: sqlite3.Connection) -> None:
    def v1() -> type:
        @dataclass(frozen=True)
        class Evolve:
            uid: int

        return Evolve

    def v2() -> type:
        @dataclass(frozen=True)
        class Evolve:
            uid: int
            extra: str | None

        return Evolve

    spec = ReaderSpec("evolve", Kind.ENTITY, ("uid",))
    old, new = v1(), v2()
    TableWriter(conn, spec, old).merge([old(1)], import_id=1)
    TableWriter(conn, spec, new).merge([new(1, "x")], import_id=2)
    for table in ("evolve", "evolve_history"):
        assert "extra" in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def test_latest_keeps_only_last_import(conn: sqlite3.Connection) -> None:
    spec = ReaderSpec("latest", Kind.LATEST)
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    TableWriter(conn, spec, Match).merge([m, m], import_id=1)
    TableWriter(conn, spec, Match).merge([m], import_id=2)
    assert conn.execute("SELECT _import_id FROM latest").fetchall() == [(2,)]


# The tables normalize() of the guide notebook gives for the 31 FM26 readers (fmsave 0.12.2),
# plus team_match_stats and squad_planner.
EXPECTED_TABLES = (
    "players players_suspensions contracts contracts_clauses contracts_chain suspensions staff "
    "staff_lists clubs clubs_teams managed_clubs finances sponsorships facilities stadiums "
    "affiliates job_vacancies nations competitions stages fixtures officials league_tables "
    "league_tables_rows league_tables_rows_matches competition_rules competition_rules_rounds "
    "transfer_windows player_match_stats team_match_stats player_season_stats "
    "player_season_history injury_types injuries training training_weeks training_weeks_days "
    "training_schedule_library mentoring tactics tactics_slots "
    "tactics_slots_in_possession_settings tactics_slots_out_of_possession_settings set_pieces "
    "selections squad_planner"
).split()


def test_every_reader_gets_the_normalize_tables() -> None:
    from fmsa.ingest.importer import RECORD_TYPES

    tables: list[str] = []
    for reader, reader_type in RECORD_TYPES.items():
        for layout in build_layout(reader_type, reader).walk():
            tables.append(layout.table)
            children = child_fields(layout.record_type)
            expected = [
                c for c in fmsave.export.column_names(layout.record_type) if c not in children
            ]
            assert layout.column_names == expected, layout.table
    assert sorted(tables) == sorted(EXPECTED_TABLES)
    assert set(CATEGORIES) == set(EXPECTED_TABLES)
