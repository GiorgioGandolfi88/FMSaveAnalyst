"""Step 0 spike: inspect what fmsave returns for one save file.

Usage:
    python spikes/inspect_save.py <save.fm> <out_dir>

Writes to <out_dir>:
    <stem>.summary.json  save info, per-reader timing/row counts/errors and a flattened schema
                         (column path, python types, null %, fmsave field status, example)
    <stem>.keys.json     identifier columns of every reader (uid, unique_id, *_id, *_uid,
                         dates, names) used later by compare_saves.py

The save is copied to a temp folder first and only read; nothing is written next to it.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import enum
import json
import shutil
import sys
import tempfile
import time
import traceback
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import fmsave
import psutil

READERS = [
    "players",
    "contracts",
    "suspensions",
    "staff",
    "staff_lists",
    "clubs",
    "managed_clubs",
    "finances",
    "sponsorships",
    "facilities",
    "stadiums",
    "affiliates",
    "job_vacancies",
    "stages",
    "competitions",
    "fixtures",
    "officials",
    "league_tables",
    "competition_rules",
    "transfer_windows",
    "player_match_stats",
    "team_match_stats",
    "player_season_stats",
    "player_season_history",
    "nations",
    "injury_types",
    "injuries",
    "training",
    "mentoring",
    "tactics",
    "set_pieces",
    "selections",
    "squad_planner",
]

SCHEMA_SAMPLE = 40_000  # max rows flattened per reader for the schema statistics
KEY_NAMES = {
    "uid",
    "unique_id",
    "id",
    "database_id",
    "date",
    "name",
    "first_name",
    "last_name",
    "full_name",
    "birth_date",
    "date_of_birth",
    "season_start_year",
    "home_goals",
    "away_goals",
    "played",
    "start_date",
    "end_date",
    "season_year",
    "kind",
    "competition_reference",
    "minutes",
    "goals",
    "starts",
    "year",
    "month",
    "wage",
    "start",
    "end",
    "ability",
    "transfer_value",
}


def is_record(value: object) -> bool:
    return dataclasses.is_dataclass(value) and not isinstance(value, type)


def scalar(value: object) -> object:
    """JSON-friendly representation of a leaf value."""
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return repr(value)


class SchemaStats:
    """Collects flattened column statistics; nested record lists become child tables."""

    def __init__(self) -> None:
        self.rows = 0
        self.cols: dict[str, dict[str, Any]] = {}
        self.children: dict[str, SchemaStats] = {}

    def col(self, path: str) -> dict[str, Any]:
        c = self.cols.get(path)
        if c is None:
            c = {"types": set(), "nulls": 0, "seen": 0, "example": None, "status": None}
            self.cols[path] = c
        return c

    def add_record(self, rec: object) -> None:
        self.rows += 1
        self._walk(rec, "")

    def _walk(self, value: object, prefix: str) -> None:
        for f in dataclasses.fields(value):  # type: ignore[arg-type]
            v = getattr(value, f.name)
            path = f"{prefix}{f.name}"
            if is_record(v):
                self._walk(v, path + ".")
                continue
            if isinstance(v, (tuple, list, frozenset, set)) and v and all(is_record(x) for x in v):
                child = self.children.setdefault(path, SchemaStats())
                for x in v:
                    child.add_record(x)
                c = self.col(path)
                c["seen"] += 1
                c["types"].add(f"list[{type(next(iter(v))).__name__}]")
                continue
            c = self.col(path)
            c["seen"] += 1
            if v is None:
                c["nulls"] += 1
                continue
            if isinstance(v, (tuple, list, frozenset, set)):
                inner = {type(x).__name__ for x in v}
                c["types"].add(f"list[{'|'.join(sorted(inner)) or '?'}]")
                if c["example"] is None and v:
                    c["example"] = [scalar(x) for x in list(v)[:5]]
            elif isinstance(v, Mapping):
                c["types"].add("map")
                if c["example"] is None and v:
                    c["example"] = {str(k): scalar(x) for k, x in list(v.items())[:5]}
            else:
                c["types"].add(type(v).__name__)
                if c["example"] is None:
                    c["example"] = scalar(v)

    def to_json(self) -> dict[str, Any]:
        return {
            "rows_sampled": self.rows,
            "columns": {
                p: {
                    "types": sorted(c["types"]),
                    "null_pct": round(100 * c["nulls"] / c["seen"], 1) if c["seen"] else None,
                    "example": c["example"],
                }
                for p, c in self.cols.items()
            },
            "children": {p: ch.to_json() for p, ch in self.children.items()},
        }


def field_statuses(record_type: type) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in dataclasses.fields(record_type):
        with contextlib.suppress(Exception):
            out[f.name] = str(fmsave.field_status(record_type, f.name))
    return out


def key_columns(table: Any) -> dict[str, list[object]]:
    """Top-level identifier-like columns of a table, every row."""
    if not len(table):
        return {}
    names = [f.name for f in dataclasses.fields(table.record_type)]
    wanted = [n for n in names if n in KEY_NAMES or n.endswith(("_uid", "_id", "_date"))]
    out = {n: [scalar(getattr(r, n)) for r in table] for n in wanted if n != "ability"}
    if "ability" in wanted:  # current/potential ability, to measure snapshot drift
        out["ability_current"] = [getattr(r.ability, "current", None) for r in table]
        out["ability_potential"] = [getattr(r.ability, "potential", None) for r in table]
    return out


def main() -> int:
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = psutil.Process()

    tmp = Path(tempfile.mkdtemp(prefix="fmsa_spike_"))
    try:
        local = tmp / src.name
        t0 = time.perf_counter()
        shutil.copy2(src, local)
        copy_s = time.perf_counter() - t0

        caught: list[str] = []
        summary: dict[str, Any] = {
            "file": src.name,
            "size_mb": round(src.stat().st_size / 2**20, 1),
            "copy_s": round(copy_s, 2),
            "readers": {},
        }
        keys: dict[str, Any] = {}
        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            t0 = time.perf_counter()
            with fmsave.open(local) as save:
                summary["open_s"] = round(time.perf_counter() - t0, 2)
                info = save.info
                summary["info"] = {
                    "game": info.game,
                    "build": info.build,
                    "build_number": info.build_number,
                    "known_build": info.known_build,
                    "db_version": info.db_version,
                    "game_date": scalar(info.game_date),
                    "time_slot": info.time_slot,
                    "save_name": info.save_name,
                    "summary_strings": list(info.summary_strings),
                    "section_count": len(info.sections),
                }
                for name in READERS:
                    entry: dict[str, Any] = {}
                    t0 = time.perf_counter()
                    try:
                        table = getattr(save, name)()
                        entry["seconds"] = round(time.perf_counter() - t0, 2)
                        entry["rows"] = len(table)
                        entry["record_type"] = table.record_type.__name__
                        entry["field_status"] = field_statuses(table.record_type)
                        try:
                            entry["coverage"] = {k: round(v, 3) for k, v in table.coverage.items()}
                        except Exception as e:
                            entry["coverage_error"] = repr(e)
                        stats = SchemaStats()
                        step = max(1, len(table) // SCHEMA_SAMPLE)
                        for rec in table[::step]:
                            stats.add_record(rec)
                        entry["schema"] = stats.to_json()
                        keys[name] = key_columns(table)
                        del table
                    except Exception as e:
                        entry["seconds"] = round(time.perf_counter() - t0, 2)
                        entry["error"] = f"{type(e).__name__}: {e}"
                        entry["traceback"] = traceback.format_exc(limit=3)
                    entry["rss_mb"] = round(proc.memory_info().rss / 2**20)
                    summary["readers"][name] = entry
                    print(
                        f"  {name:24s} {entry.get('rows', 'ERR'):>8} rows "
                        f"{entry['seconds']:>6}s rss={entry['rss_mb']}MB",
                        flush=True,
                    )
            caught = [f"{w.category.__name__}: {w.message}" for w in wlist]
        summary["warnings"] = sorted(set(caught))
        mi = proc.memory_info()
        summary["peak_mb"] = round(getattr(mi, "peak_wset", mi.rss) / 2**20)
        summary["total_s"] = round(sum(r["seconds"] for r in summary["readers"].values()), 1)

        stem = src.stem.replace(" ", "_")
        (out_dir / f"{stem}.summary.json").write_text(
            json.dumps(summary, indent=1, ensure_ascii=False, default=scalar), encoding="utf-8"
        )
        (out_dir / f"{stem}.keys.json").write_text(
            json.dumps(keys, ensure_ascii=False, default=scalar), encoding="utf-8"
        )
        print(f"done {src.name}: {summary['total_s']}s readers, peak {summary['peak_mb']}MB")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
