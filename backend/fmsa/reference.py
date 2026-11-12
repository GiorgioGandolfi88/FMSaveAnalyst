"""Game reference data (names that saves do not store), per game version.

The reference database is built by reference/build_reference.py. For a save we pick the
version that best matches its build: the same version, else the closest earlier version of the
same edition, else the closest later one.
"""

from __future__ import annotations

import contextlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from fmsa.db import q

BUILD_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True, slots=True)
class ReferenceChoice:
    version: str
    exact: bool
    tables: tuple[str, ...]


def _version_tuple(text: str) -> tuple[int, int, int] | None:
    m = BUILD_RE.match(text)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def _open(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def choose_version(reference_db: Path, build: str) -> ReferenceChoice | None:
    """Best reference version for a save build such as '26.3.2+2329565'."""
    wanted = _version_tuple(build)
    if wanted is None or not reference_db.is_file():
        return None
    with contextlib.closing(_open(reference_db)) as conn:
        versions = [
            (v, (ma, mi, pa))
            for v, ma, mi, pa in conn.execute("SELECT version, major, minor, patch FROM versions")
            if ma == wanted[0]
        ]
        if not versions:
            return None
        earlier = [x for x in versions if x[1] <= wanted]
        version, vt = (
            max(earlier, key=lambda x: x[1]) if earlier else min(versions, key=lambda x: x[1])
        )
        tables = tuple(
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'versions' "
                "ORDER BY name"
            )
        )
    return ReferenceChoice(version=version, exact=vt == wanted, tables=tables)


def competition_names(reference_db: Path, choice: ReferenceChoice) -> dict[int, str]:
    if "competitions" not in choice.tables:
        return {}
    with contextlib.closing(_open(reference_db)) as conn:
        return {
            int(i): str(n)
            for i, n in conn.execute(
                "SELECT database_id, name FROM competitions WHERE version = ? AND name IS NOT NULL",
                (choice.version,),
            )
        }


def copy_into_career(conn: sqlite3.Connection, reference_db: Path, choice: ReferenceChoice) -> int:
    """Replace the career's ref_* tables with the chosen version. Returns the rows copied.

    Runs inside the caller's transaction (ATTACH is not allowed there, so rows are copied).
    """
    total = 0
    with contextlib.closing(_open(reference_db)) as ref:
        for table in choice.tables:
            cols = [
                r[1] for r in ref.execute(f"PRAGMA table_info({q(table)})") if r[1] != "version"
            ]
            types = {r[1]: r[2] for r in ref.execute(f"PRAGMA table_info({q(table)})")}
            target = q(f"ref_{table}")
            conn.execute(f"DROP TABLE IF EXISTS {target}")
            ddl = ", ".join(f"{q(c)} {types[c]}" for c in cols)
            conn.execute(f"CREATE TABLE {target} ({ddl}, PRIMARY KEY (database_id))")
            col_sql = ", ".join(q(c) for c in cols)
            rows = ref.execute(
                f"SELECT {col_sql} FROM {q(table)} WHERE version = ?", (choice.version,)
            ).fetchall()
            marks = ", ".join("?" * len(cols))
            conn.executemany(f"INSERT INTO {target} VALUES ({marks})", rows)
            total += len(rows)
    return total
