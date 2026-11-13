"""Write fmsave tables into a career database, merging with what earlier imports stored.

Each reader has a table named like the reader (`players`) and one table per list of
sub-records (`league_tables_rows`, ...): see fmsa.ingest.schema. The tables hold the CURRENT
state. What earlier imports stored and later changed is moved, never lost:

- ENTITY / SNAPSHOT readers: replaced versions and older snapshots go to `<table>_history`
  (same columns, plus `_valid_to` = the import that replaced them); the view `<table>_all` is
  current + history together;
- EVENT readers accumulate in the table itself across imports (a save only keeps a window);
- LATEST readers keep only the last import.

Every row carries `_import_id`, the import that wrote it. The idx keys (`players_idx`,
`rows_idx`, ...) are positions within that import, so a child joins its parent on
`_import_id` + the parent's idx keys. A child row always moves together with its parent.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from hashlib import blake2b
from typing import Any

from fmsa.db import q
from fmsa.ingest.readers import Kind, ReaderSpec
from fmsa.ingest.schema import Layout, build_layout, child_records, make_rows

BATCH = 5000
CHUNK = 500

TOP_META: dict[Kind, list[tuple[str, str]]] = {
    Kind.ENTITY: [("_key", "INTEGER"), ("_hash", "INTEGER")],
    Kind.EVENT: [("_key", "INTEGER"), ("_hash", "INTEGER"), ("_first_seen", "INTEGER"),
                 ("_last_seen", "INTEGER")],
    Kind.SNAPSHOT: [],
    Kind.LATEST: [],
}  # fmt: skip
HISTORY_KINDS = frozenset({Kind.ENTITY, Kind.SNAPSHOT})
# Columns dashboards and typical queries filter on.
FILTER_COLUMNS = frozenset(
    {"club_uid", "player_uid", "competition_id", "season_year", "home_club_uid", "away_club_uid",
     "team_id", "uid"}
)  # fmt: skip

Tree = tuple[tuple[Any, ...], tuple[tuple["Tree", ...], ...]]


def h64(obj: object) -> int:
    """Stable signed 64-bit hash (fits an SQLite INTEGER)."""
    return int.from_bytes(blake2b(repr(obj).encode(), digest_size=8).digest(), "big", signed=True)


def history_table(table: str) -> str:
    return f"{table}_history"


def all_view(table: str) -> str:
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
        self.layout = build_layout(record_type, spec.name)
        self.history = spec.kind in HISTORY_KINDS
        self.row_makers: dict[str, Callable[[Iterable[Any]], Iterator[tuple[Any, ...]]]] = {
            layout.table: make_rows(layout) for layout in self.layout.walk()
        }
        names = self.layout.column_names
        missing = [k for k in spec.key if k not in names]
        if missing:
            raise ValueError(f"{spec.name}: key columns {missing} are not columns of {names[:5]}")
        self.key_idx = [names.index(k) for k in spec.key]
        self.next_rid: dict[str, int] = {}
        self.buffers: dict[str, list[tuple[Any, ...]]] = {}
        self.import_id = 0
        # per destination table (parents first): records read / rows written
        self.read_counts: dict[str, int] = {}
        self.insert_counts: dict[str, int] = {}
        self.parents: dict[str, str | None] = {}
        for layout in self.layout.walk():
            self.read_counts[layout.table] = 0
            self.insert_counts[layout.table] = 0
            self.parents[layout.table] = layout.parent.table if layout.parent else None

    @property
    def tables(self) -> list[str]:
        return list(self.read_counts)

    def layouts(self) -> dict[str, Layout]:
        return {layout.table: layout for layout in self.layout.walk()}

    # ------------------------------------------------------------------ DDL

    def _cols(self, layout: Layout) -> list[tuple[str, str]]:
        meta = TOP_META[self.spec.kind] if layout is self.layout else []
        return [("_rid", "INTEGER PRIMARY KEY"), ("_import_id", "INTEGER"), *meta,
                *((k, "INTEGER") for k in layout.keys),
                *((c.name, c.sql_type) for c in layout.columns)]  # fmt: skip

    def ensure_tables(self) -> None:
        for table, layout in self.layouts().items():
            cols = self._cols(layout)
            self._ensure(table, cols, layout)
            if self.history:
                self._ensure(history_table(table), [*cols, ("_valid_to", "INTEGER")], layout)
            self.next_rid[table] = self._max_rid(table) + 1

    def _ensure(self, table: str, cols: list[tuple[str, str]], layout: Layout) -> None:
        existing = {r[1] for r in self.conn.execute(f"PRAGMA table_info({q(table)})")}
        if not existing:
            ddl = ", ".join(f"{q(n)} {t}".rstrip() for n, t in cols)
            self.conn.execute(f"CREATE TABLE {q(table)} ({ddl})")
        else:
            for n, t in cols:
                if n not in existing:
                    self.conn.execute(f"ALTER TABLE {q(table)} ADD COLUMN {q(n)} {t}".rstrip())
        # joins: a child on its parent's keys, every descendant on the top-level key
        self._index(table, ["_import_id", *layout.keys])
        if layout.parent is not None:
            self._index(table, ["_import_id", *layout.parent.keys])
        names = {n for n, _ in cols}
        if layout is not self.layout:
            return
        if "_key" in names:
            self._index(table, ["_key"])
        if self.spec.key:
            self._index(table, list(self.spec.key))
        for col in sorted(names & FILTER_COLUMNS):
            if col not in self.spec.key[:1]:
                self._index(table, [col])

    def _index(self, table: str, columns: list[str]) -> None:
        name = f"ix_{table}_{'_'.join(columns)}"
        cols = ", ".join(q(c) for c in columns)
        self.conn.execute(f"CREATE INDEX IF NOT EXISTS {q(name)} ON {q(table)} ({cols})")

    def _max_rid(self, table: str) -> int:
        best = 0
        for t in (table, history_table(table)) if self.history else (table,):
            row = self.conn.execute(f"SELECT max(_rid) FROM {q(t)}").fetchone()
            best = max(best, int(row[0] or 0))
        return best

    def _columns(self, table: str) -> list[str]:
        return [r[1] for r in self.conn.execute(f"PRAGMA table_info({q(table)})")]

    def ensure_views(self) -> list[str]:
        """`<table>_all` = current rows + history (for readers that keep history)."""
        if not self.history:
            return []
        made = []
        for table in self.layouts():
            cols = ", ".join(q(c) for c in self._columns(table))
            view = all_view(table)
            self.conn.execute(f"DROP VIEW IF EXISTS {q(view)}")
            self.conn.execute(
                f"CREATE VIEW {q(view)} AS SELECT {cols}, NULL AS _valid_to FROM {q(table)} "
                f"UNION ALL SELECT {cols}, _valid_to FROM {q(history_table(table))}"
            )
            made.append(view)
        return made

    # ------------------------------------------------------------------ data

    def _trees(self, layout: Layout, records: Sequence[Any]) -> Iterator[Tree]:
        self.read_counts[layout.table] += len(records)
        rows = self.row_makers[layout.table](records)
        children = layout.children
        for record, row in zip(records, rows, strict=True):
            kids = tuple(
                tuple(self._trees(child, child_records(record, child))) for child in children
            )
            yield (row, kids)

    def _push(self, table: str, row: tuple[Any, ...]) -> None:
        self.insert_counts[table] += 1
        buf = self.buffers.setdefault(table, [])
        buf.append(row)
        if len(buf) >= BATCH:
            self._flush(table)

    def _flush(self, table: str) -> None:
        buf = self.buffers.get(table)
        if not buf:
            return
        marks = ", ".join("?" * len(buf[0]))
        self.conn.executemany(f"INSERT INTO {q(table)} VALUES ({marks})", buf)
        buf.clear()

    def flush_all(self) -> None:
        for table in list(self.buffers):
            self._flush(table)

    def _new_rid(self, table: str) -> int:
        rid = self.next_rid[table]
        self.next_rid[table] = rid + 1
        return rid

    def _insert(self, tree: Tree, idx: int, meta: tuple[Any, ...]) -> None:
        table = self.layout.table
        self._push(table, (self._new_rid(table), self.import_id, *meta, idx, *tree[0]))
        self._insert_children(self.layout, (idx,), tree)

    def _insert_children(self, layout: Layout, keys: tuple[int, ...], tree: Tree) -> None:
        for child, subtrees in zip(layout.children, tree[1], strict=True):
            table = child.table
            for ordinal, sub in enumerate(subtrees):
                sub_keys = (*keys, ordinal)
                self._push(table, (self._new_rid(table), self.import_id, *sub_keys, *sub[0]))
                self._insert_children(child, sub_keys, sub)

    def _move_all(self, valid_to: int, keep: bool) -> None:
        """Every row of every table of this reader to history (or away)."""
        for table in self.layouts():
            if keep:
                cols = ", ".join(q(c) for c in self._columns(table))
                self.conn.execute(
                    f"INSERT INTO {q(history_table(table))} ({cols}, _valid_to) "
                    f"SELECT {cols}, ? FROM {q(table)}",
                    (valid_to,),
                )
            self.conn.execute(f"DELETE FROM {q(table)}")

    def _remove(self, rids: list[int], valid_to: int | None, keep: bool) -> None:
        """Delete top-level rows and their descendants; with `keep`, copy them to history."""
        top = self.layout.table
        top_key = self.layout.own_key
        self.conn.execute("CREATE TEMP TABLE IF NOT EXISTS _fmsa_gone (import_id, idx)")
        self.conn.execute("DELETE FROM _fmsa_gone")
        for start in range(0, len(rids), CHUNK):
            chunk = rids[start : start + CHUNK]
            marks = ", ".join("?" * len(chunk))
            self.conn.execute(
                f"INSERT INTO _fmsa_gone SELECT _import_id, {q(top_key)} FROM {q(top)} "
                f"WHERE _rid IN ({marks})",
                chunk,
            )
        where = f"(_import_id, {q(top_key)}) IN (SELECT import_id, idx FROM _fmsa_gone)"
        for table in self.layouts():
            if keep:
                cols = ", ".join(q(c) for c in self._columns(table))
                self.conn.execute(
                    f"INSERT INTO {q(history_table(table))} ({cols}, _valid_to) "
                    f"SELECT {cols}, ? FROM {q(table)} WHERE {where}",
                    (valid_to,),
                )
            self.conn.execute(f"DELETE FROM {q(table)} WHERE {where}")
        self.conn.execute("DELETE FROM _fmsa_gone")

    def merge(self, records: Sequence[Any], import_id: int) -> MergeStats:
        self.ensure_tables()
        self.import_id = import_id
        kind = self.spec.kind
        stats = MergeStats()
        top = q(self.layout.table)
        if kind in (Kind.SNAPSHOT, Kind.LATEST):
            old = self.conn.execute(f"SELECT count(*) FROM {top}").fetchone()[0]
            if old:
                self._move_all(import_id, keep=kind is Kind.SNAPSHOT)
            stats.closed = old if kind is Kind.SNAPSHOT else 0
            for idx, tree in enumerate(self._trees(self.layout, records)):
                self._insert(tree, idx, ())
                stats.rows += 1
            stats.inserted = stats.rows
            self.flush_all()
            return stats

        if kind is Kind.ENTITY:
            sql = f"SELECT _key, _rid, _hash, NULL FROM {top}"
        else:
            sql = f"SELECT _key, _rid, _hash, _first_seen FROM {top}"
        existing: dict[int, tuple[int, int, int]] = {
            k: (rid, h, first) for k, rid, h, first in self.conn.execute(sql)
        }
        seen: set[int] = set()
        occurrences: dict[Any, int] = {}
        touched: list[tuple[int, int]] = []  # (import_id, rid) for EVENT last_seen
        replaced: list[int] = []
        new: list[tuple[Tree, int, tuple[Any, ...]]] = []

        for idx, tree in enumerate(self._trees(self.layout, records)):
            stats.rows += 1
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
                replaced.append(old[0])
                first = old[2]
            meta = (key, row_hash) if kind is Kind.ENTITY else (key, row_hash, first, import_id)
            new.append((tree, idx, meta))

        # remove replaced versions first: their children are found by (_import_id, idx)
        if kind is Kind.ENTITY:
            gone = [v[0] for k, v in existing.items() if k not in seen]
            stats.closed = len(gone)
            if replaced or gone:
                self._remove(replaced + gone, import_id, keep=True)
        elif replaced:
            self._remove(replaced, None, keep=False)
        for tree, idx, meta in new:
            self._insert(tree, idx, meta)
        self.flush_all()
        if touched:
            self.conn.executemany(f"UPDATE {top} SET _last_seen = ? WHERE _rid = ?", touched)
        return stats
