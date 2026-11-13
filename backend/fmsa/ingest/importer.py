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
from typing import Any

import fmsave

from fmsa import __version__
from fmsa.db import SCHEMA_VERSION, open_writer, q
from fmsa.ingest.readers import ALL_READERS, READER_GROUPS, READER_NAMES, ReaderSpec
from fmsa.ingest.store import MergeStats, TableWriter, history_table
from fmsa.reference import ReferenceChoice, choose_version, competition_names, copy_into_career

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
    reference_version: str | None = None
    reference_exact: bool = False

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
    started_at TEXT, finished_at TEXT, duration_s REAL, status TEXT, log_file TEXT
);
CREATE TABLE IF NOT EXISTS _import_log (
    import_id INTEGER, seq INTEGER, reader TEXT, fmsave_call TEXT, table_name TEXT,
    parent_table TEXT, storage TEXT, started_at TEXT, read_finished_at TEXT, finished_at TEXT,
    read_ms INTEGER, write_ms INTEGER, rows_read INTEGER, rows_inserted INTEGER,
    rows_updated INTEGER, rows_unchanged INTEGER, rows_closed INTEGER, status TEXT, message TEXT,
    PRIMARY KEY (import_id, seq)
);
CREATE TABLE IF NOT EXISTS _import_readers (
    import_id INTEGER, reader TEXT, status TEXT, rows INTEGER, inserted INTEGER,
    updated INTEGER, unchanged INTEGER, closed INTEGER, seconds REAL, message TEXT,
    PRIMARY KEY (import_id, reader)
);
CREATE TABLE IF NOT EXISTS _tables (
    table_name TEXT PRIMARY KEY, base_table TEXT, reader TEXT, kind TEXT,
    parent_table TEXT, record_type TEXT, key_columns TEXT, join_columns TEXT
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


def writer_for(conn: sqlite3.Connection, spec: ReaderSpec) -> TableWriter:
    return TableWriter(conn, spec, RECORD_TYPES[spec.name])


def table_of(reader: str) -> str:
    """The table a reader's records are stored in (named like the reader)."""
    return reader


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """Log fmsave's open-time warnings (e.g. unverified build) instead of printing them."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield
    for w in {f"{w.category.__name__}: {w.message}" for w in caught}:
        log.info("fmsave: %s", w)


def _now() -> str:
    return dt.datetime.now().isoformat(sep=" ", timespec="milliseconds")


class ImportLog:
    """Detailed, human-readable log of one import, written as it happens."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._fh = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = path.open("a", encoding="utf-8")

    def line(self, text: str) -> None:
        log.info("%s", text)
        if self._fh:
            self._fh.write(f"{_now()}  {text}\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


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
    if meta.get("schema_version") != str(SCHEMA_VERSION):
        raise ImportRejected(
            "This career was created by an older FMSaveAnalyst with a different database "
            "format: create a new career."
        )
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
    for table, layout in writer.layouts().items():
        top = layout is writer.layout
        parent = layout.parent
        join = ["_import_id", *parent.keys] if parent else []
        conn.execute(
            "INSERT OR REPLACE INTO _tables VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                table,
                history_table(table) if writer.history else None,
                spec.name,
                spec.kind.value if top else "child",
                parent.table if parent else None,
                layout.record_type.__name__,
                json.dumps(list(spec.key) if top else layout.keys),
                json.dumps(join) if join else None,
            ),
        )
        conn.execute("DELETE FROM _columns WHERE table_name = ?", (table,))
        conn.executemany(
            "INSERT INTO _columns VALUES (?, ?, ?, ?, ?, ?)",
            [
                (table, c.name, c.sql_type, ".".join((table, *c.path)), c.status, i)
                for i, c in enumerate(layout.columns)
            ],
        )


def import_save(
    db_path: Path,
    save_path: Path,
    *,
    reference_db: Path | None = None,
    career_name: str | None = None,
    progress: Progress | None = None,
    readers: tuple[str, ...] | None = None,
    log_dir: Path | None = None,
) -> ImportResult:
    """Import `save_path` into the career database `db_path` (created if missing).

    `log_dir` receives a detailed text log of the import (also stored in `_import_log`).

    `reference_db` supplies the names saves do not store (see fmsa.reference).
    `readers` limits the import to some readers (partial import). The others are recorded in
    `_import_readers` as "skipped": their tables exist (possibly empty) and keep what earlier
    imports stored.
    """
    started = time.perf_counter()
    if readers is not None:
        unknown = sorted(set(readers) - set(READER_NAMES))
        if unknown:
            raise ValueError(f"unknown readers: {', '.join(unknown)}")
        if not readers:
            raise ValueError("no readers selected")
    groups = [tuple(r for r in g if readers is None or r.name in readers) for g in READER_GROUPS]
    groups = [g for g in groups if g]
    total = sum(len(g) for g in groups)
    skipped = tuple(r for r in ALL_READERS if readers is not None and r.name not in readers)

    with tempfile.TemporaryDirectory(prefix="fmsa_import_") as tmp:
        local = Path(tmp) / save_path.name
        sha = _copy_with_hash(save_path, local)
        with _quiet(), fmsave.open(local) as save:
            info = save.info
        choice = choose_version(reference_db, info.build) if reference_db else None
        names = competition_names(reference_db, choice) if reference_db and choice else None

        conn = open_writer(db_path)
        try:
            conn.executescript(META_DDL)
            _check_compatible(conn, info, sha)
            conn.execute("BEGIN")
            ilog = ImportLog(None)
            try:
                ilog = _open_log(conn, db_path, log_dir)
                result = _run_import(
                    conn, local, save_path, sha, info, groups, total, names, progress, ilog,
                    skipped,
                )
                selected = [r.name for g in groups for r in g]
                conn.execute(
                    "INSERT OR REPLACE INTO _meta VALUES ('import_readers', ?)",
                    (json.dumps(selected),),
                )
                if career_name:
                    conn.execute(
                        "INSERT OR REPLACE INTO _meta VALUES ('career_name', ?)", (career_name,)
                    )
                if reference_db and choice:
                    _apply_reference(conn, reference_db, choice)
                    result.reference_version = choice.version
                    result.reference_exact = choice.exact
                conn.execute("COMMIT")
                ilog.line(f"COMMIT import #{result.import_id}")
            except BaseException as exc:
                conn.execute("ROLLBACK")
                ilog.line(f"FAILED, nothing was saved (rollback): {type(exc).__name__}: {exc}")
                raise
            finally:
                ilog.close()
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
    ilog: ImportLog,
    skipped: tuple[ReaderSpec, ...] = (),
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
    if ilog.path:
        conn.execute(
            "UPDATE _imports SET log_file = ? WHERE import_id = ?", (str(ilog.path), import_id)
        )
    ilog.line(f"IMPORT #{import_id} START  file={source}  sha256={sha}")
    ilog.line(
        f"  game={info.game} build={info.build} known_build={info.known_build} "
        f"db_version={info.db_version} game_date={info.game_date} save_name={info.save_name!r}"
    )
    ilog.line(f"  fmsave {fmsave.__version__}, FMSaveAnalyst {__version__}, readers={total}")
    results: list[ReaderResult] = []
    done = 0
    seq = 0
    for group in groups:
        with _quiet(), fmsave.open(local, competition_names=competition_names) as save:
            for spec in group:
                if progress:
                    progress(spec.name, done, total)
                result, seq = _import_reader(conn, save, spec, import_id, ilog, seq)
                results.append(result)
                done += 1
    if progress:
        progress("", done, total)
    for spec in skipped:
        # not selected: tables exist (queries keep working) and keep earlier imports' rows
        writer = writer_for(conn, spec)
        writer.ensure_tables()
        _write_catalog(conn, writer)
        conn.execute(
            f"INSERT INTO _import_readers VALUES ({', '.join('?' * 10)})",
            (import_id, spec.name, "skipped", 0, 0, 0, 0, 0, 0.0, "not selected for this import"),
        )
    if skipped:
        ilog.line(f"SKIPPED (not selected): {', '.join(s.name for s in skipped)}")

    total_read = sum(r.stats.rows for r in results)
    ilog.line(
        f"READERS DONE  ok={sum(r.status == 'ok' for r in results)} "
        f"unsupported={sum(r.status == 'unsupported' for r in results)} "
        f"error={sum(r.status == 'error' for r in results)}  records read={total_read}"
    )
    views: list[str] = []
    for spec in ALL_READERS:
        if spec.name in RECORD_TYPES and _has_table(conn, table_of(spec.name)):
            views += writer_for(conn, spec).ensure_views()
    ilog.line(f"HISTORY VIEWS ({len(views)}): {', '.join(views)}")
    ilog.line("TABLES: " + ", ".join(f"{t}={n}" for t, n in table_counts(conn).items()))

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


def _apply_reference(conn: sqlite3.Connection, reference_db: Path, choice: ReferenceChoice) -> None:
    rows = copy_into_career(conn, reference_db, choice)
    conn.executemany(
        "INSERT OR REPLACE INTO _meta VALUES (?, ?)",
        [("reference_version", choice.version), ("reference_exact", str(int(choice.exact)))],
    )
    if "nations" in choice.tables and _has_table(conn, "nations"):
        conn.execute("DROP VIEW IF EXISTS nation_names")
        conn.execute(
            "CREATE VIEW nation_names AS SELECT n.nation_id, n.database_id, r.name, "
            "r.short_name, r.code FROM nations n "
            "LEFT JOIN ref_nations r ON r.database_id = n.database_id"
        )
    log.info("Reference data %s (exact=%s): %d rows", choice.version, choice.exact, rows)


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def _open_log(conn: sqlite3.Connection, db_path: Path, log_dir: Path | None) -> ImportLog:
    if log_dir is None:
        return ImportLog(None)
    row = conn.execute("SELECT coalesce(max(import_id), 0) + 1 FROM _imports").fetchone()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return ImportLog(log_dir / f"{db_path.stem}_import{row[0]:03d}_{stamp}.log")


def _read(save: fmsave.Save, spec: ReaderSpec) -> list[Any] | Any:
    target = getattr(save, spec.fmsave_name)
    if spec.source == "property":
        return [target]
    if spec.source == "method":
        return [target()]
    return target()


def _call_name(spec: ReaderSpec) -> str:
    suffix = "" if spec.source == "property" else "()"
    return f"Save.{spec.fmsave_name}{suffix}"


def _import_reader(
    conn: sqlite3.Connection,
    save: fmsave.Save,
    spec: ReaderSpec,
    import_id: int,
    ilog: ImportLog,
    seq: int,
) -> tuple[ReaderResult, int]:
    started_at = _now()
    t0 = time.perf_counter()
    result = ReaderResult(spec.name, "ok")
    writer = writer_for(conn, spec)
    data: Any = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            data = _read(save, spec)
        except Exception as exc:  # a reader fmsave cannot read must not stop the import
            unsupported = isinstance(exc, fmsave.UnsupportedGameError)
            result.status = "unsupported" if unsupported else "error"
            result.message = f"{type(exc).__name__}: {exc}"
    read_finished_at = _now()
    t1 = time.perf_counter()
    rows_from_reader = len(data) if data is not None else 0
    if data is not None:
        result.stats = writer.merge(data, import_id)
        del data
    else:
        writer.ensure_tables()  # empty tables keep views and queries valid
    notes = sorted({f"{w.category.__name__}: {w.message}" for w in caught})
    if notes:
        result.message = "\n".join(filter(None, [result.message, *notes]))
    finished_at = _now()
    t2 = time.perf_counter()
    result.seconds = round(t2 - t0, 3)
    read_ms, write_ms = round((t1 - t0) * 1000), round((t2 - t1) * 1000)
    _write_catalog(conn, writer)
    s = result.stats
    conn.execute(
        f"INSERT INTO _import_readers VALUES ({', '.join('?' * 10)})",
        (import_id, spec.name, result.status, s.rows, s.inserted, s.updated, s.unchanged,
         s.closed, result.seconds, result.message or None),
    )  # fmt: skip

    ilog.line(
        f"READER {spec.name} [{_call_name(spec)}] status={result.status} "
        f"start={started_at} read_end={read_finished_at} end={finished_at} "
        f"read={read_ms}ms write={write_ms}ms records_from_reader={rows_from_reader}"
    )
    if result.message:
        ilog.line(f"  message: {result.message}")
    for table in writer.tables:
        seq += 1
        top = table == writer.layout.table
        read = writer.read_counts[table]
        inserted = writer.insert_counts[table]
        parent = writer.parents.get(table)
        conn.execute(
            f"INSERT INTO _import_log VALUES ({', '.join('?' * 19)})",
            (import_id, seq, spec.name, _call_name(spec), table, parent,
             spec.kind.value if top else "child", started_at, read_finished_at, finished_at,
             read_ms, write_ms, rows_from_reader if top else read, inserted,
             s.updated if top else None, s.unchanged if top else None,
             s.closed if top else None, result.status, result.message or None),
        )  # fmt: skip
        extra = f" updated={s.updated} unchanged={s.unchanged} closed={s.closed}" if top else ""
        ilog.line(
            f"  -> table {table:<28} read={(rows_from_reader if top else read):>9} "
            f"inserted={inserted:>9}{extra}"
        )
    return result, seq


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Rows of every record-type table (current state)."""
    names = [r[0] for r in conn.execute("SELECT table_name FROM _tables ORDER BY table_name")]
    return {n: conn.execute(f"SELECT count(*) FROM {q(n)}").fetchone()[0] for n in names}
