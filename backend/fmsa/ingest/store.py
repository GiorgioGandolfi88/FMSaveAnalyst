"""Write fmsave tables into a career database, merging with what earlier imports stored."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from hashlib import blake2b
from typing import Any

from fmsa.db import q
from fmsa.ingest.readers import Kind, ReaderSpec
from fmsa.ingest.schema import Layout, build_layout, child_records, make_flattener

BATCH = 5000

META_COLUMNS: dict[Kind, list[tuple[str, str]]] = {
    Kind.ENTITY: [("_key", "INTEGER"), ("_hash", "INTEGER"), ("_valid_from", "INTEGER"),
                  ("_valid_to", "INTEGER")],
    Kind.EVENT: [("_key", "INTEGER"), ("_hash", "INTEGER"), ("_first_seen", "INTEGER"),
                 ("_last_seen", "INTEGER")],
    Kind.SNAPSHOT: [("_import_id", "INTEGER")],
    Kind.LATEST: [("_import_id", "INTEGER")],
}  # fmt: skip
CHILD_META: list[tuple[str, str]] = [("_parent_rid", "INTEGER"), ("_ord", "INTEGER")]

Tree = tuple[tuple[Any, ...], tuple[tuple["Tree", ...], ...]]


def h64(obj: object) -> int:
    """Stable signed 64-bit hash (fits an SQLite INTEGER)."""
    return int.from_bytes(blake2b(repr(obj).encode(), digest_size=8).digest(), "big", signed=True)


def base_table(table: str) -> str:
    return f"{table}_all"


@dataclass(slots=True)
class MergeStats:
    rows: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    closed: int = 0


class TableWriter:
    """Creates/extends the tables of one reader and merges a fmsave Table into them."""

    def __init__(self, conn: sqlite3.Connection, spec: ReaderSpec, record_type: type) -> None:
        self.conn = conn
        self.spec = spec
        self.layout = build_layout(spec.name, record_type, spec.exclude)
        self.flatteners: dict[str, Callable[[Any], tuple[Any, ...]]] = {}
        self._layouts: list[Layout] = []
        self._collect(self.layout)
        names = self.layout.column_names
        missing = [k for k in spec.key if k not in names]
        if missing:
            raise ValueError(f"{spec.name}: key columns {missing} are not top-level columns")
        self.key_idx = [names.index(k) for k in spec.key]
        self.next_rid: dict[str, int] = {}
        self.buffers: dict[str, list[tuple[Any, ...]]] = {}

    def _collect(self, layout: Layout) -> None:
        self._layouts.append(layout)
        self.flatteners[layout.table] = make_flattener(layout)
        for _, child in layout.children:
            self._collect(child)

    @property
    def layouts(self) -> list[Layout]:
        return self._layouts

    # ------------------------------------------------------------------ DDL

    def ensure_tables(self) -> None:
        for layout in self._layouts:
            meta = META_COLUMNS[self.spec.kind] if layout is self.layout else CHILD_META
            self._ensure(base_table(layout.table), meta, layout)
            self.next_rid[layout.table] = self._max_rid(layout.table) + 1

    def _ensure(self, table: str, meta: list[tuple[str, str]], layout: Layout) -> None:
        cols = [("_rid", "INTEGER PRIMARY KEY"), *meta,
                *((c.name, c.sql_type) for c in layout.columns)]  # fmt: skip
        existing = {r[1] for r in self.conn.execute(f"PRAGMA table_info({q(table)})")}
        if not existing:
            ddl = ", ".join(f"{q(n)} {t}" for n, t in cols)
            self.conn.execute(f"CREATE TABLE {q(table)} ({ddl})")
        else:
            for n, t in cols:
                if n not in existing:
                    self.conn.execute(f"ALTER TABLE {q(table)} ADD COLUMN {q(n)} {t}")
        idx = {
            Kind.ENTITY: ["_key", "_valid_to"],
            Kind.EVENT: ["_key"],
            Kind.SNAPSHOT: ["_import_id"],
            Kind.LATEST: ["_import_id"],
        }[self.spec.kind]
        if layout is not self.layout:
            idx = ["_parent_rid"]
        self._index(table, idx)
        if layout is self.layout and self.spec.key:
            self._index(table, list(self.spec.key))

    def _index(self, table: str, columns: list[str]) -> None:
        name = f"ix_{table}_{'_'.join(columns)}"
        cols = ", ".join(q(c) for c in columns)
        self.conn.execute(f"CREATE INDEX IF NOT EXISTS {q(name)} ON {q(table)} ({cols})")

    def _max_rid(self, table: str) -> int:
        row = self.conn.execute(f"SELECT max(_rid) FROM {q(base_table(table))}").fetchone()
        return int(row[0] or 0)

    def ensure_views(self) -> None:
        top = self.layout.table
        base = q(base_table(top))
        if self.spec.kind is Kind.ENTITY:
            body = f"SELECT * FROM {base} WHERE _valid_to IS NULL"
        elif self.spec.kind in (Kind.EVENT, Kind.LATEST):
            body = f"SELECT * FROM {base}"
        else:
            body = (
                f"SELECT * FROM {base} WHERE _import_id = (SELECT max(import_id) "
                f"FROM _import_readers WHERE reader = '{top}' AND status = 'ok')"
            )
        self._view(top, body)
        self._child_views(self.layout)

    def _child_views(self, parent: Layout) -> None:
        for _, child in parent.children:
            body = (
                f"SELECT * FROM {q(base_table(child.table))} "
                f"WHERE _parent_rid IN (SELECT _rid FROM {q(parent.table)})"
            )
            self._view(child.table, body)
            self._child_views(child)

    def _view(self, name: str, body: str) -> None:
        self.conn.execute(f"DROP VIEW IF EXISTS {q(name)}")
        self.conn.execute(f"CREATE VIEW {q(name)} AS {body}")

    # ------------------------------------------------------------------ data

    def _tree(self, layout: Layout, record: Any) -> Tree:
        row = self.flatteners[layout.table](record)
        kids = tuple(
            tuple(self._tree(child, r) for r in child_records(record, path))
            for path, child in layout.children
        )
        return (row, kids)

    def _push(self, table: str, row: tuple[Any, ...]) -> None:
        buf = self.buffers.setdefault(table, [])
        buf.append(row)
        if len(buf) >= BATCH:
            self._flush(table)

    def _flush(self, table: str) -> None:
        buf = self.buffers.get(table)
        if not buf:
            return
        marks = ", ".join("?" * len(buf[0]))
        self.conn.executemany(f"INSERT INTO {q(base_table(table))} VALUES ({marks})", buf)
        buf.clear()

    def flush_all(self) -> None:
        for table in list(self.buffers):
            self._flush(table)

    def _insert(self, tree: Tree, meta: tuple[Any, ...]) -> int:
        table = self.layout.table
        rid = self.next_rid[table]
        self.next_rid[table] = rid + 1
        self._push(table, (rid, *meta, *tree[0]))
        self._insert_children(self.layout, rid, tree)
        return rid

    def _insert_children(self, layout: Layout, parent_rid: int, tree: Tree) -> None:
        for (_, child), subtrees in zip(layout.children, tree[1], strict=True):
            for ordinal, sub in enumerate(subtrees):
                rid = self.next_rid[child.table]
                self.next_rid[child.table] = rid + 1
                self._push(child.table, (rid, parent_rid, ordinal, *sub[0]))
                self._insert_children(child, rid, sub)

    def _delete(self, rids: Sequence[int]) -> None:
        """Delete top-level rows and all their descendants."""
        self._delete_rows(self.layout, list(rids), top=True)

    def _delete_rows(self, layout: Layout, rids: list[int], top: bool) -> None:
        for chunk_start in range(0, len(rids), 500):
            chunk = rids[chunk_start : chunk_start + 500]
            marks = ", ".join("?" * len(chunk))
            for _, child in layout.children:
                child_rids = [
                    r[0]
                    for r in self.conn.execute(
                        f"SELECT _rid FROM {q(base_table(child.table))} "
                        f"WHERE _parent_rid IN ({marks})",
                        chunk,
                    )
                ]
                self._delete_rows(child, child_rids, top=False)
            self.conn.execute(
                f"DELETE FROM {q(base_table(layout.table))} WHERE _rid IN ({marks})", chunk
            )

    def merge(self, records: Iterable[Any], import_id: int) -> MergeStats:
        self.ensure_tables()
        kind = self.spec.kind
        stats = MergeStats()
        if kind is Kind.LATEST:
            for layout in self._layouts:
                self.conn.execute(f"DELETE FROM {q(base_table(layout.table))}")
        if kind in (Kind.SNAPSHOT, Kind.LATEST):
            for record in records:
                self._insert(self._tree(self.layout, record), (import_id,))
                stats.rows += 1
            stats.inserted = stats.rows
            self.flush_all()
            return stats

        base = q(base_table(self.layout.table))
        if kind is Kind.ENTITY:
            sql = f"SELECT _key, _rid, _hash, _valid_from FROM {base} WHERE _valid_to IS NULL"
        else:
            sql = f"SELECT _key, _rid, _hash, _first_seen FROM {base}"
        existing: dict[int, tuple[int, int, int]] = {
            k: (rid, h, first) for k, rid, h, first in self.conn.execute(sql)
        }
        seen: set[int] = set()
        occurrences: dict[Any, int] = {}
        touched: list[tuple[int, int]] = []  # (import_id, rid) for EVENT last_seen
        to_close: list[int] = []
        to_delete: list[int] = []

        for record in records:
            stats.rows += 1
            tree = self._tree(self.layout, record)
            row_hash = h64(tree)
            base_key: Any = tuple(tree[0][i] for i in self.key_idx) if self.key_idx else row_hash
            n = occurrences.get(base_key, 0)
            occurrences[base_key] = n + 1
            key = h64((base_key, n))
            seen.add(key)
            old = existing.get(key)
            if old is not None and old[1] == row_hash:
                stats.unchanged += 1
                if kind is Kind.EVENT:
                    touched.append((import_id, old[0]))
                continue
            if old is None:
                first = import_id
                stats.inserted += 1
            else:
                stats.updated += 1
                if kind is Kind.ENTITY:
                    to_close.append(old[0])
                    first = import_id
                else:
                    to_delete.append(old[0])
                    first = old[2]
            self._insert(tree, (key, row_hash, first, import_id if kind is Kind.EVENT else None))

        if kind is Kind.ENTITY:
            gone = [v[0] for k, v in existing.items() if k not in seen]
            stats.closed = len(gone)
            to_close.extend(gone)
        self.flush_all()
        if to_close:
            self.conn.executemany(
                f"UPDATE {base} SET _valid_to = ? WHERE _rid = ?",
                [(import_id, rid) for rid in to_close],
            )
        if to_delete:
            self._delete(to_delete)
        if touched:
            self.conn.executemany(f"UPDATE {base} SET _last_seen = ? WHERE _rid = ?", touched)
        return stats
