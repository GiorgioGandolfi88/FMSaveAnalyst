"""Build reference/fm_reference.sqlite from the CSV files in reference/src/.

    python reference/build_reference.py [--src reference/src] [--out reference/fm_reference.sqlite]

Layout of the sources (one folder per game version, e.g. 26.3.2 or 27.0.1):

    reference/src/26.3.2/competitions.csv
    reference/src/26.3.2/nations.csv
    reference/src/26.3.2/cities.csv
    reference/src/26.3.2/<anything>.csv

Every CSV is UTF-8 with a header row and must have a `database_id` column (the id of the game
database). Each file becomes a table of the same name with an extra `version` column; columns
named `database_id` or ending in `_id` are stored as integers, the others as text.
The career database receives a copy of the version that best matches the save's build.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def column_type(name: str) -> str:
    return "INTEGER" if name == "database_id" or name.endswith("_id") else "TEXT"


def convert(value: str, sql_type: str) -> object:
    value = value.strip()
    if value == "":
        return None
    if sql_type == "INTEGER":
        return int(value)
    return value


def build(src: Path, out: Path) -> dict[str, int]:
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        counts = _fill(conn, src)
        conn.commit()
    except BaseException:
        conn.close()
        tmp.unlink(missing_ok=True)
        raise
    conn.close()
    tmp.replace(out)
    return counts


def _fill(conn: sqlite3.Connection, src: Path) -> dict[str, int]:
    conn.execute(
        "CREATE TABLE versions (version TEXT PRIMARY KEY, game TEXT, major INTEGER, "
        "minor INTEGER, patch INTEGER)"
    )
    tables: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    for folder in sorted(p for p in src.iterdir() if p.is_dir()):
        m = VERSION_RE.match(folder.name)
        if not m:
            raise SystemExit(f"{folder}: folder name must be a version like 26.3.2")
        major, minor, patch = (int(g) for g in m.groups())
        conn.execute(
            "INSERT INTO versions VALUES (?, ?, ?, ?, ?)",
            (folder.name, f"FM{major}", major, minor, patch),
        )
        for file in sorted(folder.glob("*.csv")):
            table = file.stem.lower()
            if not NAME_RE.match(table) or table == "versions":
                raise SystemExit(f"{file}: invalid table name '{table}'")
            with file.open(encoding="utf-8-sig", newline="") as fh:
                reader = csv.reader(fh)
                header = [h.strip().lower() for h in next(reader, [])]
                if "database_id" not in header:
                    raise SystemExit(f"{file}: missing 'database_id' column")
                if table not in tables:
                    tables[table] = header
                    cols = ", ".join(f"{q(h)} {column_type(h)}" for h in header)
                    conn.execute(
                        f"CREATE TABLE {q(table)} (version TEXT NOT NULL, {cols}, "
                        "PRIMARY KEY (version, database_id))"
                    )
                elif tables[table] != header:
                    raise SystemExit(f"{file}: columns differ from other versions of '{table}'")
                types = [column_type(h) for h in header]
                rows = []
                for line_no, row in enumerate(reader, start=2):
                    if not any(c.strip() for c in row):
                        continue
                    if len(row) != len(header):
                        raise SystemExit(f"{file}:{line_no}: expected {len(header)} values")
                    try:
                        rows.append(
                            (folder.name, *(convert(v, t) for v, t in zip(row, types, strict=True)))
                        )
                    except ValueError as exc:
                        raise SystemExit(f"{file}:{line_no}: {exc}") from exc
                marks = ", ".join("?" * (len(header) + 1))
                try:
                    conn.executemany(f"INSERT INTO {q(table)} VALUES ({marks})", rows)
                except sqlite3.IntegrityError as exc:
                    raise SystemExit(f"{file}: duplicate database_id ({exc})") from exc
                counts[f"{folder.name}/{table}"] = len(rows)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=HERE / "src")
    parser.add_argument("--out", type=Path, default=HERE / "fm_reference.sqlite")
    args = parser.parse_args(argv)
    counts = build(args.src, args.out)
    for name, n in counts.items():
        print(f"{name:40s} {n:>7d}")
    print(f"Written {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
