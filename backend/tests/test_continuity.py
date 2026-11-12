"""Continuity verdicts, evaluated on a small hand-made career database."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from fmsa.ingest.continuity import _evaluate
from fmsa.ingest.importer import META_DDL

CONFIG = "765,MALE,5,0"


@dataclass
class FakeInfo:
    game: str = "FM26"
    build: str = "26.3.2+1"
    game_date: dt.date | None = dt.date(2027, 6, 15)
    summary_strings: tuple[str, ...] = (CONFIG, "26.3.2+1", "Serie B", "Mario Rossi")


@pytest.fixture
def career(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "c.fmsa")
    conn.executescript(META_DDL)
    conn.executemany("INSERT INTO _meta VALUES (?, ?)", [("game", "FM26"), ("game_config", CONFIG)])
    conn.execute(
        "INSERT INTO _imports (file_name, sha256, game, build, game_date, summary_strings, status) "
        "VALUES ('s1.fm', 'aaa', 'FM26', '26.3.2+1', '2026-06-15', ?, 'ok')",
        (json.dumps([CONFIG, "26.3.2+1", "Serie B", "Mario Rossi"]),),
    )
    conn.execute("CREATE TABLE clubs (uid, unique_id)")
    conn.executemany("INSERT INTO clubs VALUES (?, ?)", [(i, 1000 + i) for i in range(100)])
    conn.execute(
        "CREATE TABLE fixtures (date, home_team_id, away_team_id, home_goals, away_goals, played)"
    )
    conn.executemany(
        "INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, 1)",
        [(f"2026-03-{d:02d}", d, d + 1, 1, 0) for d in range(1, 21)],
    )
    return conn


CLUBS = {i: 1000 + i for i in range(100)}
SAME_FIXTURES = [(f"2026-03-{d:02d}", d, d + 1, 1, 0) for d in range(1, 21)]


def outcome(report, check_id: str) -> str:  # type: ignore[no-untyped-def]
    return next(c.outcome for c in report.checks if c.id == check_id)


def test_same_career(career: sqlite3.Connection) -> None:
    r = _evaluate(career, "s2.fm", "bbb", FakeInfo(), CLUBS, SAME_FIXTURES)  # type: ignore[arg-type]
    assert r.verdict == "same"
    assert not r.gap_warning


def test_gap_still_same_but_warned(career: sqlite3.Connection) -> None:
    later = [("2028-01-10", 1, 2, 0, 0)]
    r = _evaluate(career, "s4.fm", "ccc", FakeInfo(), CLUBS, later)  # type: ignore[arg-type]
    assert r.verdict == "same"
    assert r.gap_warning


def test_different_results_mean_another_career(career: sqlite3.Connection) -> None:
    other = [(d, h, a, 3, 3) for d, h, a, _, _ in SAME_FIXTURES]
    info = FakeInfo(summary_strings=(CONFIG, "26.3.2+1", "Serie C", "Luca Bianchi"))
    r = _evaluate(career, "x.fm", "ddd", info, CLUBS, other)  # type: ignore[arg-type]
    assert r.verdict == "different"
    assert outcome(r, "fixtures") == "fail"


def test_other_setup_is_different(career: sqlite3.Connection) -> None:
    info = FakeInfo(summary_strings=("1,MALE,1,0", "26.3.2+1"))
    clubs = {i: 5000 + i for i in range(100)}
    r = _evaluate(career, "x.fm", "eee", info, clubs, [])  # type: ignore[arg-type]
    assert r.verdict == "different"


@pytest.mark.parametrize(
    ("info", "sha", "failed"),
    [
        (FakeInfo(game="FM27"), "fff", "game"),
        (FakeInfo(game_date=dt.date(2026, 6, 15)), "fff", "date"),
        (FakeInfo(), "aaa", "not_imported"),
    ],
)
def test_hard_requirements(
    career: sqlite3.Connection, info: FakeInfo, sha: str, failed: str
) -> None:
    r = _evaluate(career, "x.fm", sha, info, CLUBS, SAME_FIXTURES)  # type: ignore[arg-type]
    assert r.verdict == "incompatible"
    assert outcome(r, failed) == "fail"
