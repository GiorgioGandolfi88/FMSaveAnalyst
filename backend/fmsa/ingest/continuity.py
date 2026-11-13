"""Is a save the continuation of the career stored in a database?

The signals come from the Step 0 spike (docs/fmsave-schema.md §4):

hard requirements (any failure => "incompatible", the import is refused)
  - same game edition
  - in-game date after the last import
  - not the exact same file again

evidence (decides "same" / "uncertain" / "different")
  - game configuration string stored in the save summary (identical for a whole career)
  - other summary strings (human manager name, loaded leagues)
  - club uid -> game database id map (identical for a whole career)
  - matches already in the database that fall inside the new save's window must have the same
    result; a different career has the same calendar but different results
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import tempfile
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import fmsave

from fmsa.ingest.importer import _copy_with_hash, career_info, last_import

Verdict = Literal["same", "uncertain", "different", "incompatible"]
Outcome = Literal["pass", "fail", "warn", "skip"]


@dataclass(slots=True)
class Check:
    id: str
    outcome: Outcome
    detail: str
    hard: bool = False


@dataclass(slots=True)
class ContinuityReport:
    verdict: Verdict
    save_file: str
    save_game: str
    save_build: str
    save_date: str | None
    career_date: str | None
    checks: list[Check] = field(default_factory=list)
    gap_warning: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def check_continuity(db_path: Path, save_path: Path) -> ContinuityReport:
    with tempfile.TemporaryDirectory(prefix="fmsa_check_") as tmp:
        local = Path(tmp) / save_path.name
        sha = _copy_with_hash(save_path, local)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with fmsave.open(local) as save:
                info = save.info
                clubs = None
                fixtures = None
                with contextlib.suppress(Exception):
                    clubs = {c.uid: c.unique_id for c in save.clubs()}
                with contextlib.suppress(Exception):
                    fixtures = [
                        (f.date.isoformat(), f.home_team_id, f.away_team_id,
                         f.home_goals, f.away_goals)
                        for f in save.fixtures()
                        if f.played and f.date is not None
                    ]  # fmt: skip
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            return _evaluate(conn, save_path.name, sha, info, clubs, fixtures)
        finally:
            conn.close()


def _evaluate(
    conn: sqlite3.Connection,
    file_name: str,
    sha: str,
    info: fmsave.SaveInfo,
    clubs: dict[int, int | None] | None,
    fixtures: list[tuple[str, int, int, int | None, int | None]] | None,
) -> ContinuityReport:
    meta = career_info(conn)
    last = last_import(conn)
    save_date = info.game_date.isoformat() if info.game_date else None
    report = ContinuityReport(
        verdict="uncertain",
        save_file=file_name,
        save_game=info.game,
        save_build=info.build,
        save_date=save_date,
        career_date=last["game_date"] if last else None,
    )
    checks = report.checks

    # ---- hard requirements
    same_game = meta.get("game") == info.game
    checks.append(Check("game", "pass" if same_game else "fail",
                        f"{info.game} / {meta.get('game')}", hard=True))  # fmt: skip
    if last and save_date and last["game_date"]:
        later = save_date > last["game_date"]
        checks.append(Check("date", "pass" if later else "fail",
                            f"{save_date} > {last['game_date']}", hard=True))  # fmt: skip
    dup = conn.execute(
        "SELECT file_name FROM _imports WHERE sha256 = ? AND status = 'ok'", (sha,)
    ).fetchone()
    checks.append(Check("not_imported", "fail" if dup else "pass", dup[0] if dup else "", True))
    if any(c.hard and c.outcome == "fail" for c in checks):
        report.verdict = "incompatible"
        return report

    # ---- evidence
    strong = 0
    against = 0
    config = info.summary_strings[0] if info.summary_strings else ""
    if meta.get("game_config"):
        same_config = config == meta["game_config"]
        checks.append(Check("game_config", "pass" if same_config else "fail", ""))
        strong += same_config
        against += not same_config

    if last and last["summary_strings"]:
        previous = set(json.loads(last["summary_strings"])) - {last["build"]}
        current = set(info.summary_strings) - {info.build}
        common = len(previous & current)
        ok = _ratio(common, len(previous)) >= 0.5
        checks.append(Check("summary", "pass" if ok else "warn", f"{common}/{len(previous)}"))

    if clubs is None:
        checks.append(Check("clubs", "skip", "clubs not readable"))
    else:
        stored = dict(conn.execute("SELECT uid, unique_id FROM Club").fetchall())
        shared = clubs.keys() & stored.keys()
        same = sum(1 for u in shared if clubs[u] == stored[u])
        ratio = _ratio(same, max(len(stored), len(clubs)))
        outcome: Outcome = "pass" if ratio >= 0.99 else ("warn" if ratio >= 0.9 else "fail")
        checks.append(Check("clubs", outcome, f"{ratio:.1%}"))
        against += outcome == "fail"

    if fixtures is None:
        checks.append(Check("fixtures", "skip", "fixtures not readable"))
    else:
        stored_fx = {
            (d, h, a): (hg, ag)
            for d, h, a, hg, ag in conn.execute(
                "SELECT date, home_team_id, away_team_id, home_goals, away_goals "
                "FROM Fixture WHERE played = 1"
            )
        }
        overlap: list[tuple[tuple[str, int, int], tuple[int | None, int | None]]] = []
        for d, h, a, hg, ag in fixtures:
            if (d, h, a) in stored_fx:
                overlap.append(((d, h, a), (hg, ag)))
        matching = sum(1 for k, v in overlap if stored_fx[k] == v)
        if not overlap:
            checks.append(Check("fixtures", "warn", "0"))
            report.gap_warning = bool(stored_fx)
        else:
            ratio = _ratio(matching, len(overlap))
            ok = ratio >= 0.95
            checks.append(Check("fixtures", "pass" if ok else "fail",
                                f"{matching}/{len(overlap)}"))  # fmt: skip
            strong += ok
            against += not ok

    if against:
        report.verdict = "different"
    elif strong >= 1 and not any(c.outcome == "fail" for c in checks):
        report.verdict = "same"
    return report
