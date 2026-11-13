"""Career databases on disk, save files to import, and background import jobs."""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fmsa.db import CAREER_SUFFIX, open_writer
from fmsa.ingest.importer import ImportRejected, ImportResult, import_save

log = logging.getLogger(__name__)

SAVE_SUFFIX = ".fm"
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def career_file_name(name: str) -> str:
    cleaned = _UNSAFE.sub("_", name).strip(" .")
    if not cleaned:
        raise ValueError("empty career name")
    return cleaned[:120] + CAREER_SUFFIX


@dataclass(slots=True)
class CareerSummary:
    path: str
    name: str
    game: str | None
    imports: int
    first_game_date: str | None
    last_game_date: str | None
    last_save: str | None
    manager: str | None
    reference_version: str | None
    size_mb: float
    error: str | None = None
    import_readers: list[str] | None = None  # readers chosen at the last import (None: all)


def read_summary(path: Path) -> CareerSummary:
    summary = CareerSummary(
        path=str(path),
        name=path.stem,
        game=None,
        imports=0,
        first_game_date=None,
        last_game_date=None,
        last_save=None,
        manager=None,
        reference_version=None,
        size_mb=round(path.stat().st_size / 2**20, 1) if path.exists() else 0.0,
    )
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with contextlib.closing(sqlite3.connect(uri, uri=True)) as conn:
            meta = dict(conn.execute("SELECT key, value FROM _meta").fetchall())
            summary.name = meta.get("career_name") or path.stem
            summary.game = meta.get("game")
            summary.reference_version = meta.get("reference_version")
            if meta.get("import_readers"):
                with contextlib.suppress(ValueError):
                    summary.import_readers = list(json.loads(meta["import_readers"]))
            row = conn.execute(
                "SELECT count(*), min(game_date), max(game_date) FROM _imports WHERE status = 'ok'"
            ).fetchone()
            summary.imports, summary.first_game_date, summary.last_game_date = row
            last = conn.execute(
                "SELECT file_name, manager_name FROM _imports WHERE status = 'ok' "
                "ORDER BY import_id DESC LIMIT 1"
            ).fetchone()
            if last:
                summary.last_save, summary.manager = last
    except sqlite3.Error as exc:
        summary.error = str(exc)
    return summary


def list_careers(folder: Path, extra: list[str]) -> list[CareerSummary]:
    paths: dict[str, Path] = {}
    if folder.is_dir():
        for p in folder.glob(f"*{CAREER_SUFFIX}"):
            paths[str(p.resolve()).lower()] = p
    for e in extra:
        p = Path(e)
        if p.is_file():
            paths.setdefault(str(p.resolve()).lower(), p)
    careers = [read_summary(p) for p in paths.values()]
    return sorted(careers, key=lambda c: (c.last_game_date or "", c.name), reverse=True)


def import_history(path: Path) -> list[dict[str, Any]]:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        imports = [
            dict(r)
            for r in conn.execute(
                "SELECT import_id, file_name, game_date, build, finished_at, duration_s, status, "
                "manager_name FROM _imports ORDER BY import_id DESC"
            )
        ]
        problems: dict[int, list[dict[str, Any]]] = {}
        for r in conn.execute(
            "SELECT import_id, reader, status, message FROM _import_readers WHERE status != 'ok'"
        ):
            problems.setdefault(r["import_id"], []).append(dict(r))
    for imp in imports:
        imp["skipped_readers"] = problems.get(imp["import_id"], [])
    return imports


def import_log(path: Path, import_id: int) -> dict[str, Any]:
    """Per-reader, per-table detail of one import (see `_import_log`)."""
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        imp = conn.execute(
            "SELECT import_id, file_name, started_at, finished_at, duration_s, status, log_file "
            "FROM _imports WHERE import_id = ?",
            (import_id,),
        ).fetchone()
        try:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM _import_log WHERE import_id = ? ORDER BY seq", (import_id,)
                )
            ]
        except sqlite3.OperationalError:  # careers created before the detailed log existed
            rows = []
    return {"import": dict(imp) if imp else None, "rows": rows}


@dataclass(slots=True)
class SaveFile:
    path: str
    name: str
    size_mb: float
    modified: str


def list_saves(folder: Path) -> list[SaveFile]:
    if not folder.is_dir():
        return []
    files = [p for p in folder.rglob(f"*{SAVE_SUFFIX}") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        SaveFile(
            path=str(p),
            name=p.stem,
            size_mb=round(p.stat().st_size / 2**20, 1),
            modified=dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes"),
        )
        for p in files[:500]
    ]


# ---------------------------------------------------------------------------- rename / delete


class CareerFileError(Exception):
    """A career cannot be renamed or deleted (name taken, file in use, ...)."""


SIDE_FOLDERS = ("queries", "shortlists")  # per-career files kept in the data folder


def career_side_file(data_dir: Path, career: Path, folder: str) -> Path:
    digest = hashlib.sha1(str(career.resolve()).lower().encode()).hexdigest()[:8]
    return data_dir / folder / f"{career.stem}-{digest}.json"


def saved_queries_file(data_dir: Path, career: Path) -> Path:
    return career_side_file(data_dir, career, "queries")


def _sqlite_files(path: Path) -> list[Path]:
    return [path, Path(f"{path}-wal"), Path(f"{path}-shm")]


def _import_logs(path: Path, log_dir: Path | None) -> list[Path]:
    """Text logs of the career's imports (as recorded in `_imports.log_file`, plus any file of
    the log folder named after the career)."""
    found: dict[str, Path] = {}
    with contextlib.suppress(sqlite3.Error):
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with contextlib.closing(sqlite3.connect(uri, uri=True)) as conn:
            for (f,) in conn.execute("SELECT log_file FROM _imports WHERE log_file IS NOT NULL"):
                p = Path(f)
                if p.is_file():
                    found[str(p).lower()] = p
    if log_dir and log_dir.is_dir():
        for p in log_dir.glob(f"{glob_escape(path.stem)}_import*.log"):
            found.setdefault(str(p).lower(), p)
    return list(found.values())


def glob_escape(text: str) -> str:
    return re.sub(r"([\[\]*?])", r"[\1]", text)


def career_files(path: Path, data_dir: Path, log_dir: Path | None) -> list[Path]:
    """Every file that belongs to a career: database, SQLite side files, saved queries, logs."""
    files = [p for p in _sqlite_files(path) if p.exists()]
    for folder in SIDE_FOLDERS:
        side = career_side_file(data_dir, path, folder)
        if side.is_file():
            files.append(side)
    return files + _import_logs(path, log_dir)


def rename_career(path: Path, new_name: str, data_dir: Path, log_dir: Path | None) -> Path:
    """Rename a career: its display name, its database file and the files named after it."""
    try:
        target = path.with_name(career_file_name(new_name))
    except ValueError as exc:
        raise CareerFileError(str(exc)) from exc
    same_file = str(target).lower() == str(path).lower()
    if target.exists() and not same_file:
        raise CareerFileError(f"a career file named {target.name} already exists")
    old_sides = {f: career_side_file(data_dir, path, f) for f in SIDE_FOLDERS}
    logs = _import_logs(path, log_dir)
    try:
        conn = open_writer(path)
    except sqlite3.Error as exc:
        raise CareerFileError(str(exc)) from exc
    try:
        conn.execute("INSERT OR REPLACE INTO _meta VALUES ('career_name', ?)", (new_name.strip(),))
        if not same_file:
            for log in logs:
                if log.name.startswith(f"{path.stem}_import"):
                    new_log = log.with_name(target.stem + log.name[len(path.stem) :])
                    conn.execute(
                        "UPDATE _imports SET log_file = ? WHERE log_file = ?",
                        (str(new_log), str(log)),
                    )
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    if same_file:
        if target.name != path.name:  # only the letter case changes
            path.rename(target)
        return target
    try:
        path.rename(target)
    except OSError as exc:
        raise CareerFileError(f"the career file is in use: {exc}") from exc
    for side in ("-wal", "-shm"):
        Path(f"{path}{side}").unlink(missing_ok=True)
    for folder, old in old_sides.items():
        if old.is_file():
            old.replace(career_side_file(data_dir, target, folder))
    for log in logs:
        if log.name.startswith(f"{path.stem}_import"):
            with contextlib.suppress(OSError):
                log.rename(log.with_name(target.stem + log.name[len(path.stem) :]))
    return target


def delete_career(path: Path, data_dir: Path, log_dir: Path | None) -> list[str]:
    """Delete a career database and every file that belongs to it. Returns the deleted paths."""
    files = career_files(path, data_dir, log_dir)
    try:
        path.unlink()
    except OSError as exc:
        raise CareerFileError(f"the career file is in use: {exc}") from exc
    deleted = [str(path)]
    for f in files[1:]:
        with contextlib.suppress(OSError):
            f.unlink()
            deleted.append(str(f))
    return deleted


# ---------------------------------------------------------------------------- jobs


@dataclass(slots=True)
class Job:
    id: str
    kind: str
    career_path: str
    save_path: str
    status: str = "running"  # running | done | rejected | failed
    reader: str = ""
    done: int = 0
    total: int = 0
    started: float = field(default_factory=time.time)
    finished: float | None = None
    message: str = ""
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["elapsed_s"] = round((self.finished or time.time()) - self.started, 1)
        return d


def _result_dict(r: ImportResult) -> dict[str, Any]:
    return {
        "import_id": r.import_id,
        "file_name": r.file_name,
        "game_date": r.game_date,
        "seconds": r.seconds,
        "reference_version": r.reference_version,
        "reference_exact": r.reference_exact,
        "readers": [
            {"reader": x.reader, "status": x.status, "rows": x.stats.rows, "message": x.message}
            for x in r.readers
        ],
    }


class JobRunner:
    """Runs one import at a time in a background thread."""

    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def busy_with(self, career: Path) -> bool:
        """An import into `career` is running."""
        job = self._jobs.get(self._active or "")
        return bool(
            job and job.status == "running" and job.career_path.lower() == str(career).lower()
        )

    def start(
        self,
        kind: str,
        career: Path,
        save: Path,
        reference_db: Path | None,
        career_name: str | None = None,
        readers: tuple[str, ...] | None = None,
    ) -> Job:
        with self._lock:
            if self._active and self._jobs[self._active].status == "running":
                raise RuntimeError("another import is already running")
            job = Job(uuid.uuid4().hex[:12], kind, str(career), str(save))
            self._jobs[job.id] = job
            self._active = job.id

        def progress(reader: str, done: int, total: int) -> None:
            job.reader, job.done, job.total = reader, done, total

        def work() -> None:
            try:
                result = import_save(
                    career,
                    save,
                    reference_db=reference_db,
                    career_name=career_name,
                    progress=progress,
                    readers=readers,
                    log_dir=self.log_dir,
                )
                job.result = _result_dict(result)
                job.status = "done"
            except ImportRejected as exc:
                job.status, job.message = "rejected", str(exc)
            except Exception as exc:
                log.exception("Import failed")
                job.status = "failed"
                job.message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"
                if kind == "create":
                    _discard_new_career(career)
            finally:
                job.finished = time.time()

        threading.Thread(target=work, daemon=True, name=f"import-{job.id}").start()
        return job


def _discard_new_career(path: Path) -> None:
    """Remove the database file of a career whose first import failed (it holds no data)."""
    with contextlib.suppress(Exception):
        if read_summary(path).imports == 0:
            for p in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
                p.unlink(missing_ok=True)
