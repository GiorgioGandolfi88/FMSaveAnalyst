"""Career databases on disk, save files to import, and background import jobs."""

from __future__ import annotations

import contextlib
import datetime as dt
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

from fmsa.db import CAREER_SUFFIX
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

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def start(
        self,
        kind: str,
        career: Path,
        save: Path,
        reference_db: Path | None,
        career_name: str | None = None,
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
