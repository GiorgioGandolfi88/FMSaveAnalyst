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
from fmsa.ingest.schema import build_layout
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


def test_layout_uses_fmsave_column_names() -> None:
    layout = build_layout(Person)
    assert layout.table == "Person"
    assert tuple(layout.column_names) == fmsave.export.column_names(Person)
    assert [(c.field, c.kind, c.layout.table) for c in layout.children] == [
        ("ability", "group", "Ability"),
        ("traits", "list", "Trait"),
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
    current = conn.execute("SELECT uid, ability_current, _valid_from FROM Person ORDER BY uid")
    assert current.fetchall() == [(1, 110, 2), (3, 80, 2)]
    history = conn.execute(
        "SELECT uid, ability_current, _valid_from, _valid_to FROM Person_history ORDER BY uid"
    )
    assert history.fetchall() == [(1, 100, 1, 2), (2, 90, 1, 2)]
    assert conn.execute("SELECT count(*) FROM Person_all").fetchone()[0] == 4
    # nested records follow their parent
    assert conn.execute("SELECT count(*) FROM Ability").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM Ability_history").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM Trait").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM Trait_history").fetchone()[0] == 3
    row = conn.execute(
        "SELECT a._parent_table, a._parent_field, p.uid, a.current FROM Ability a "
        "JOIN Person p ON p._rid = a._parent_rid ORDER BY p.uid"
    ).fetchall()
    assert row == [("Person", "ability", 1, 110), ("Person", "ability", 3, 80)]
    assert conn.execute(
        "SELECT positions, foot, foot_code, unknown_x, traits FROM Person WHERE uid = 1"
    ).fetchone() == ('["ST","AMC"]', "left", 1, 1, '[{"code":0,"name":"t0"}]')


def test_child_change_creates_new_version(conn: sqlite3.Connection) -> None:
    TableWriter(conn, PEOPLE, Person).merge([person(1, 100, traits=1)], import_id=1)
    s = TableWriter(conn, PEOPLE, Person).merge([person(1, 100, traits=2)], import_id=2)
    assert s.updated == 1
    assert conn.execute("SELECT count(*) FROM Trait").fetchone()[0] == 2


def test_events_accumulate_and_update(conn: sqlite3.Connection) -> None:
    first = [Match(dt.date(2026, 1, 1), 1, 2, 1, 0), Match(dt.date(2026, 2, 1), 2, 1, None, None)]
    TableWriter(conn, MATCHES, Match).merge(first, import_id=1)
    second = [Match(dt.date(2026, 2, 1), 2, 1, 2, 2), Match(dt.date(2026, 3, 1), 1, 3, None, None)]
    w = TableWriter(conn, MATCHES, Match)
    s = w.merge(second, import_id=2)
    assert w.ensure_views() == []  # events keep everything in the table itself
    assert (s.inserted, s.updated, s.unchanged) == (1, 1, 0)
    rows = conn.execute(
        "SELECT date, home_goals, _first_seen, _last_seen FROM Match ORDER BY date"
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
    assert conn.execute("SELECT count(*) FROM Match").fetchone()[0] == 2


def test_snapshot_keeps_last_copy_and_history(conn: sqlite3.Connection) -> None:
    spec = ReaderSpec("snap", Kind.SNAPSHOT)
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    TableWriter(conn, spec, Match).merge([m], import_id=1)
    w = TableWriter(conn, spec, Match)
    w.merge([m, m], import_id=2)
    w.ensure_views()
    assert conn.execute("SELECT _import_id FROM Match").fetchall() == [(2,), (2,)]
    assert conn.execute("SELECT _import_id, _valid_to FROM Match_history").fetchall() == [(1, 2)]
    assert conn.execute("SELECT count(*) FROM Match_all").fetchone()[0] == 3


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
    for table in ("Evolve", "Evolve_history"):
        assert "extra" in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def test_latest_keeps_only_last_import(conn: sqlite3.Connection) -> None:
    spec = ReaderSpec("latest", Kind.LATEST)
    m = Match(dt.date(2026, 1, 1), 1, 2, 0, 0)
    TableWriter(conn, spec, Match).merge([m, m], import_id=1)
    TableWriter(conn, spec, Match).merge([m], import_id=2)
    assert conn.execute("SELECT _import_id FROM Match").fetchall() == [(2,)]


# The record types of fmsave's documentation, each must get a table of its own.
DOCUMENTED_TYPES = (
    "Player Attributes Ability Reputation Positions Personality Contract Clause "
    "ContractChainEntry PlayerSuspension Suspension Staff StaffAttributes StaffPreferences "
    "StaffList Club Team ClubFacilities Stadium FinanceMonth Sponsorship AffiliateGroup "
    "JobVacancy Nation Stage Competition Fixture Official LeagueTable LeagueTableSplit "
    "LeagueTableMatch LeagueTableRow TransferWindow CompetitionRules RulesRound PlayerMatchStats "
    "TeamMatchStats PlayerSeasonStats PlayerSeasonHistory InjuryType InjuryRecord ManagedClub "
    "Tactic TacticSlot TacticSettingUnit SetPieceRoutine Selection TeamTraining TrainingSchedule "
    "TrainingWeek TrainingDay MentoringGroup SquadPlannerSlot"
).split()


def test_every_documented_type_gets_a_table_with_fmsave_columns() -> None:
    from fmsa.ingest.importer import RECORD_TYPES, SKIP_GROUPS

    tables: dict[str, list[str]] = {}
    for reader_type in RECORD_TYPES.values():
        for layout in build_layout(reader_type, SKIP_GROUPS).walk():
            tables[layout.table] = layout.column_names
    for name in DOCUMENTED_TYPES:
        assert name in tables, name
        assert tuple(tables[name]) == fmsave.export.column_names(getattr(fmsave, name)), name
        assert name in CATEGORIES, name
