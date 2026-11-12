"""Import a Football Manager save into a career database.

The whole import is one transaction: if anything unexpected fails, the database is left exactly
as it was. A reader that fmsave cannot read for this build (UnsupportedGameError and similar) is
recorded in `_import_readers` and skipped; the rest of the save is still imported.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import logging
import shutil
import sqlite3
import tempfile
import time
import warnings
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import fmsave

from fmsa import __version__
from fmsa.db import SCHEMA_VERSION, open_writer, q
from fmsa.ingest.readers import ALL_READERS, READER_GROUPS, ReaderSpec
from fmsa.ingest.store import MergeStats, TableWriter, base_table

log = logging.getLogger(__name__)

Progress = Callable[[str, int, int], None]  # (reader name, readers done, readers total)


class ImportRejected(Exception):
    """The save cannot be imported into this career database (nothing was written)."""


@dataclass(slots=True)
class ReaderResult:
    reader: str
    status: str  # ok | unsupported | error
    stats: MergeStats = field(default_factory=MergeStats)
    seconds: float = 0.0
    message: str = ""


@dataclass(slots=True)
class ImportResult:
    import_id: int
    file_name: str
    game: str
    build: str
    game_date: str | None
    seconds: float
    readers: list[ReaderResult]

    @property
    def failed(self) -> list[ReaderResult]:
        return [r for r in self.readers if r.status != "ok"]


META_DDL = """
CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS _imports (
    import_id INTEGER PRIMARY KEY,
    file_name TEXT, source_path TEXT, sha256 TEXT, size_bytes INTEGER,
    game TEXT, build TEXT, build_number INTEGER, known_build INTEGER, db_version TEXT,
    game_date TEXT, save_name TEXT, summary_strings TEXT, manager_name TEXT,
    fmsave_version TEXT, app_version TEXT,
    started_at TEXT, finished_at TEXT, duration_s REAL, status TEXT
);
CREATE TABLE IF NOT EXISTS _import_readers (
    import_id INTEGER, reader TEXT, status TEXT, rows INTEGER, inserted INTEGER,
    updated INTEGER, unchanged INTEGER, closed INTEGER, seconds REAL, message TEXT,
    PRIMARY KEY (import_id, reader)
);
CREATE TABLE IF NOT EXISTS _tables (
    table_name TEXT PRIMARY KEY, base_table TEXT, reader TEXT, kind TEXT,
    parent_table TEXT, record_type TEXT, key_columns TEXT
);
CREATE TABLE IF NOT EXISTS _columns (
    table_name TEXT, column_name TEXT, sql_type TEXT, source_path TEXT, field_status TEXT,
    position INTEGER, PRIMARY KEY (table_name, column_name)
);
"""

# Reader name -> fmsave record type, needed to create empty tables for readers that fail.
RECORD_TYPES: dict[str, type] = {
    "players": fmsave.Player, "contracts": fmsave.Contract, "suspensions": fmsave.Suspension,
    "staff": fmsave.Staff, "staff_lists": fmsave.StaffList, "clubs": fmsave.Club,
    "managed_clubs": fmsave.ManagedClub, "finances": fmsave.FinanceMonth,
    "sponsorships": fmsave.Sponsorship, "facilities": fmsave.ClubFacilities,
    "stadiums": fmsave.Stadium, "affiliates": fmsave.AffiliateGroup,
    "job_vacancies": fmsave.JobVacancy, "nations": fmsave.Nation,
    "competitions": fmsave.Competition, "stages": fmsave.Stage, "fixtures": fmsave.Fixture,
    "officials": fmsave.Official, "league_tables": fmsave.LeagueTable,
    "competition_rules": fmsave.CompetitionRules, "transfer_windows": fmsave.TransferWindow,
    "player_match_stats": fmsave.PlayerMatchStats, "team_match_stats": fmsave.TeamMatchStats,
    "player_season_stats": fmsave.PlayerSeasonStats,
    "player_season_history": fmsave.PlayerSeasonHistory, "injury_types": fmsave.InjuryType,
    "injuries": fmsave.InjuryRecord, "training": fmsave.TeamTraining,
    "mentoring": fmsave.MentoringGroup, "tactics": fmsave.Tactic,
    "set_pieces": fmsave.SetPieceRoutine, "selections": fmsave.Selection,
    "squad_planner": fmsave.SquadPlannerSlot,
}  # fmt: skip


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """Log fmsave's open-time warnings (e.g. unverified build) instead of printing them."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield
    for w in {f"{w.category.__name__}: {w.message}" for w in caught}:
        log.info("fmsave: %s", w)


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _copy_with_hash(src: Path, dst: Path) -> str:
    digest = hashlib.sha256()
    with src.open("rb") as fin, dst.open("wb") as fout:
        while chunk := fin.read(8 * 1024 * 1024):
            digest.update(chunk)
            fout.write(chunk)
    shutil.copystat(src, dst)
    return digest.hexdigest()


def career_info(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        return dict(conn.execute("SELECT key, value FROM _meta").fetchall())
    except sqlite3.OperationalError:
        return {}


def last_import(conn: sqlite3.Connection) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM _imports WHERE status = 'ok' ORDER BY import_id DESC LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.row_factory = None


def _check_compatible(conn: sqlite3.Connection, info: fmsave.SaveInfo, sha: str) -> None:
    meta = career_info(conn)
    if not meta:
        return
    if meta.get("game") != info.game:
        raise ImportRejected(
            f"This career is {meta.get('game')}, the save is {info.game}: create a new career."
        )
    dup = conn.execute(
        "SELECT file_name FROM _imports WHERE sha256 = ? AND status = 'ok'", (sha,)
    ).fetchone()
    if dup:
        raise ImportRejected(f"This exact save was already imported (as {dup[0]}).")
    last = last_import(conn)
    last_date = last["game_date"] if last else None
    if info.game_date and last_date and info.game_date.isoformat() <= last_date:
        raise ImportRejected(
            f"The save is dated {info.game_date}, not after the last import ({last_date})."
        )


def _write_catalog(conn: sqlite3.Connection, writer: TableWriter) -> None:
    spec = writer.spec
    parents = {child.table: layout.table for layout in writer.layouts
               for _, child in layout.children}  # fmt: skip
    for layout in writer.layouts:
        top = layout is writer.layout
        conn.execute(
            "INSERT OR REPLACE INTO _tables VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                layout.table,
                base_table(layout.table),
                spec.name,
                spec.kind.value if top else "child",
                parents.get(layout.table),
                layout.record_type.__name__,
                json.dumps(list(spec.key)) if top else None,
            ),
        )
        conn.execute("DELETE FROM _columns WHERE table_name = ?", (layout.table,))
        conn.executemany(
            "INSERT INTO _columns VALUES (?, ?, ?, ?, ?, ?)",
            [
                (layout.table, c.name, c.sql_type, ".".join(c.path), c.status, i)
                for i, c in enumerate(layout.columns)
            ],
        )


def import_save(
    db_path: Path,
    save_path: Path,
    *,
    competition_names: Mapping[int, str] | None = None,
    progress: Progress | None = None,
    readers: tuple[str, ...] | None = None,
) -> ImportResult:
    """Import `save_path` into the career database `db_path` (created if missing).

    `readers` limits the import to some readers (used by tests).
    """
    started = time.perf_counter()
    groups = [tuple(r for r in g if readers is None or r.name in readers) for g in READER_GROUPS]
    groups = [g for g in groups if g]
    total = sum(len(g) for g in groups)

    with tempfile.TemporaryDirectory(prefix="fmsa_import_") as tmp:
        local = Path(tmp) / save_path.name
        sha = _copy_with_hash(save_path, local)
        with _quiet(), fmsave.open(local) as save:
            info = save.info

        conn = open_writer(db_path)
        try:
            conn.executescript(META_DDL)
            _check_compatible(conn, info, sha)
            conn.execute("BEGIN")
            try:
                result = _run_import(
                    conn, local, save_path, sha, info, groups, total, competition_names, progress
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()
    result.seconds = round(time.perf_counter() - started, 1)
    with contextlib.closing(open_writer(db_path)) as conn:
        conn.execute(
            "UPDATE _imports SET duration_s = ? WHERE import_id = ?",
            (result.seconds, result.import_id),
        )
    return result


def _run_import(
    conn: sqlite3.Connection,
    local: Path,
    source: Path,
    sha: str,
    info: fmsave.SaveInfo,
    groups: list[tuple[ReaderSpec, ...]],
    total: int,
    competition_names: Mapping[int, str] | None,
    progress: Progress | None,
) -> ImportResult:
    meta = career_info(conn)
    if not meta:
        conn.executemany(
            "INSERT INTO _meta VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("game", info.game),
                ("created_at", _now()),
                ("created_by", f"FMSaveAnalyst {__version__}"),
                ("first_save_name", info.save_name),
                ("game_config", info.summary_strings[0] if info.summary_strings else ""),
            ],
        )
    cur = conn.execute(
        "INSERT INTO _imports (file_name, source_path, sha256, size_bytes, game, build, "
        "build_number, known_build, db_version, game_date, save_name, summary_strings, "
        "fmsave_version, app_version, started_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')",
        (
            source.name,
            str(source),
            sha,
            source.stat().st_size,
            info.game,
            info.build,
            info.build_number,
            int(info.known_build),
            info.db_version,
            info.game_date.isoformat() if info.game_date else None,
            info.save_name,
            json.dumps(list(info.summary_strings), ensure_ascii=False),
            fmsave.__version__,
            __version__,
            _now(),
        ),
    )
    import_id = int(cur.lastrowid or 0)
    results: list[ReaderResult] = []
    done = 0
    for group in groups:
        with _quiet(), fmsave.open(local, competition_names=competition_names) as save:
            for spec in group:
                if progress:
                    progress(spec.name, done, total)
                results.append(_import_reader(conn, save, spec, import_id))
                done += 1
    if progress:
        progress("", done, total)

    for spec in ALL_READERS:
        if spec.name in RECORD_TYPES and _has_table(conn, spec.name):
            TableWriter(conn, spec, RECORD_TYPES[spec.name]).ensure_views()

    manager = None
    if _has_table(conn, "staff"):
        row = conn.execute(
            "SELECT name FROM staff WHERE is_human_manager = 1 ORDER BY _rid LIMIT 1"
        ).fetchone()
        manager = row[0] if row else None
    conn.execute(
        "UPDATE _imports SET finished_at = ?, status = 'ok', manager_name = ? WHERE import_id = ?",
        (_now(), manager, import_id),
    )
    return ImportResult(
        import_id=import_id,
        file_name=source.name,
        game=info.game,
        build=info.build,
        game_date=info.game_date.isoformat() if info.game_date else None,
        seconds=0.0,
        readers=results,
    )


def _has_table(conn: sqlite3.Connection, reader: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (base_table(reader),),
        ).fetchone()
        is not None
    )


def _import_reader(
    conn: sqlite3.Connection, save: fmsave.Save, spec: ReaderSpec, import_id: int
) -> ReaderResult:
    t0 = time.perf_counter()
    result = ReaderResult(spec.name, "ok")
    writer = TableWriter(conn, spec, RECORD_TYPES[spec.name])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            table = getattr(save, spec.name)()
        except Exception as exc:  # a reader fmsave cannot read must not stop the import
            table = None
            unsupported = isinstance(exc, fmsave.UnsupportedGameError)
            result.status = "unsupported" if unsupported else "error"
            result.message = f"{type(exc).__name__}: {exc}"
            log.warning("Reader %s skipped: %s", spec.name, result.message)
    if table is not None:
        result.stats = writer.merge(table, import_id)
        del table
    else:
        writer.ensure_tables()  # empty tables keep views and queries valid
    notes = sorted({f"{w.category.__name__}: {w.message}" for w in caught})
    if notes:
        result.message = "\n".join(filter(None, [result.message, *notes]))
    result.seconds = round(time.perf_counter() - t0, 2)
    _write_catalog(conn, writer)
    s = result.stats
    conn.execute(
        f"INSERT INTO _import_readers VALUES ({', '.join('?' * 10)})",
        (import_id, spec.name, result.status, s.rows, s.inserted, s.updated, s.unchanged,
         s.closed, result.seconds, result.message or None),
    )  # fmt: skip
    log.info(
        "%-22s %-11s rows=%d new=%d upd=%d same=%d closed=%d %.1fs",
        spec.name, result.status, s.rows, s.inserted, s.updated, s.unchanged, s.closed,
        result.seconds,
    )  # fmt: skip
    return result


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [r[0] for r in conn.execute("SELECT table_name FROM _tables ORDER BY table_name")]
    return {n: conn.execute(f"SELECT count(*) FROM {q(n)}").fetchone()[0] for n in names}
