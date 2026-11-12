"""Merge semantics of the career database store, with small synthetic record types."""

from __future__ import annotations

import datetime as dt
import enum
import sqlite3
from dataclasses import dataclass

import pytest

from fmsa.db import open_writer
from fmsa.ingest.readers import Kind, ReaderSpec
from fmsa.ingest.schema import build_layout
from fmsa.ingest.store import TableWriter


class Foot(enum.Enum):
    LEFT = 1
    RIGHT = 2


@dataclass(frozen=True)
class Coded:
    label: Foot
    raw: int


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
    uid: int
    name: str
    birth_date: dt.date
    ability: Ability
    foot: Coded | None
    positions: tuple[str, ...]
    traits: tuple[Trait, ...]
    unknown: dict[str, int]


@dataclass(frozen=True)
class Match:
    date: dt.date
    home: int
    away: int
    home_goals: int | None
    away_goals: int | None


def person(uid: int, ca: int, born: str = "2000-01-01", traits: int = 1, name: str = "") -> Person:
    return Person(
        uid=uid,
        name=name or f"P{uid}",
        birth_date=dt.date.fromisoformat(born),
        ability=Ability(ca, 180),
        foot=Coded(Foot.LEFT, 1),
        positions=("ST", "AMC"),
        traits=tuple(Trait(i, f"t{i}") for i in range(traits)),
        unknown={"x": 1},
    )


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    c = open_writer(tmp_path / "t.fmsa")
    c.execute("CREATE TABLE _import_readers (import_id, reader, status)")
    return c


PEOPLE = ReaderSpec("people", Kind.ENTITY, ("uid", "birth_date"))
MATCHES = ReaderSpec("matches", Kind.EVENT, ("date", "home", "away"))


def test_layout_flattens_nested_records() -> None:
    layout = build_layout("people", Person)
    names = layout.column_names
    assert names == [
        "uid", "name", "birth_date", "ability_current", "ability_potential",
        "foot_label", "foot_raw", "positions",
    ]  # fmt: skip
    assert [c.table for _, c in layout.children] == ["people__traits"]
    types = {c.name: c.sql_type for c in layout.columns}
    assert types["uid"] == "INTEGER" and types["birth_date"] == "TEXT"
    assert types["positions"] == "TEXT"


def test_entity_versions(conn: sqlite3.Connection) -> None:
    w = TableWriter(conn, PEOPLE, Person)
    s1 = w.merge([person(1, 100), person(2, 120)], import_id=1)
    w.ensure_views()
    assert (s1.inserted, s1.updated) == (2, 0)

    # player 1 improves, player 2 retires, a regen reuses uid 2 with another birth date
    s2 = TableWriter(conn, PEOPLE, Person).merge(
        [person(1, 110), person(2, 60, born="2010-05-05")], import_id=2
    )
    assert (s2.inserted, s2.updated, s2.closed) == (1, 1, 1)

    s3 = TableWriter(conn, PEOPLE, Person).merge(
        [person(1, 110), person(2, 60, born="2010-05-05")], import_id=3
    )
    assert (s3.unchanged, s3.inserted, s3.updated, s3.closed) == (2, 0, 0, 0)

    rows = conn.execute(
        "SELECT uid, birth_date, ability_current, _valid_from, _valid_to "
        "FROM people_all ORDER BY _rid"
    ).fetchall()
    assert rows == [
        (1, "2000-01-01", 100, 1, 2),
        (2, "2000-01-01", 120, 1, 2),
        (1, "2000-01-01", 110, 2, None),
        (2, "2010-05-05", 60, 2, None),
    ]
    current = conn.execute("SELECT uid, ability_current FROM people ORDER BY uid").fetchall()
    assert current == [(1, 110), (2, 60)]
    # children follow their parent version
    assert conn.execute("SELECT count(*) FROM people__traits_all").fetchone()[0] == 4
    assert conn.execute("SELECT count(*) FROM people__traits").fetchone()[0] == 2
    assert conn.execute("SELECT positions, foot_label FROM people LIMIT 1").fetchone() == (
        '["ST","AMC"]',
        "LEFT",
    )


def test_child_change_creates_new_version(conn: sqlite3.Connection) -> None:
    TableWriter(conn, PEOPLE, Person).merge([person(1, 100, traits=1)], import_id=1)
    s = TableWriter(conn, PEOPLE, Person).merge([person(1, 100, traits=2)], import_id=2)
    assert s.updated == 1


def test_events_accumulate_and_update(conn: sqlite3.Connection) -> None:
    d = dt.date
    first = [Match(d(2026, 1, 1), 1, 2, 1, 0), Match(d(2026, 2, 1), 3, 4, None, None)]
    TableWriter(conn, MATCHES, Match).merge(first, import_id=1)
    # the old match fell out of the save's window, the future one was played, a new one appears
    second = [Match(d(2026, 2, 1), 3, 4, 2, 2), Match(d(2026, 3, 1), 1, 3, None, None)]
    w = TableWriter(conn, MATCHES, Match)
    s = w.merge(second, import_id=2)
    w.ensure_views()
    assert (s.inserted, s.updated, s.unchanged) == (1, 1, 0)
    rows = conn.execute(
        "SELECT date, home_goals, _first_seen, _last_seen FROM matches ORDER BY date"
    ).fetchall()
    assert rows == [
        ("2026-01-01", 1, 1, 1),
        ("2026-02-01", 2, 1, 2),
        ("2026-03-01", None, 2, 2),
    ]


def test_identical_duplicates_are_kept(conn: sqlite3.Connection) -> None:
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    spec = ReaderSpec("dups", Kind.EVENT)
    TableWriter(conn, spec, Match).merge([m, m], import_id=1)
    s = TableWriter(conn, spec, Match).merge([m, m], import_id=2)
    assert s.unchanged == 2
    assert conn.execute("SELECT count(*) FROM dups_all").fetchone()[0] == 2


def test_snapshot_per_import(conn: sqlite3.Connection) -> None:
    spec = ReaderSpec("snap", Kind.SNAPSHOT)
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    TableWriter(conn, spec, Match).merge([m], import_id=1)
    w = TableWriter(conn, spec, Match)
    w.merge([m, m], import_id=2)
    conn.executemany("INSERT INTO _import_readers VALUES (?, 'snap', 'ok')", [(1,), (2,)])
    w.ensure_views()
    assert conn.execute("SELECT count(*) FROM snap_all").fetchone()[0] == 3
    assert conn.execute("SELECT count(*) FROM snap").fetchone()[0] == 2


def test_new_column_is_added(conn: sqlite3.Connection) -> None:
    @dataclass(frozen=True)
    class V1:
        uid: int

    @dataclass(frozen=True)
    class V2:
        uid: int
        extra: str | None

    spec = ReaderSpec("evolve", Kind.ENTITY, ("uid",))
    TableWriter(conn, spec, V1).merge([V1(1)], import_id=1)
    TableWriter(conn, spec, V2).merge([V2(1, "x")], import_id=2)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(evolve_all)")]
    assert "extra" in cols


def test_latest_keeps_only_last_import(conn: sqlite3.Connection) -> None:
    spec = ReaderSpec("latest", Kind.LATEST)
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    TableWriter(conn, spec, Match).merge([m, m], import_id=1)
    w = TableWriter(conn, spec, Match)
    w.merge([m], import_id=2)
    w.ensure_views()
    assert conn.execute("SELECT _import_id FROM latest").fetchall() == [(2,)]
