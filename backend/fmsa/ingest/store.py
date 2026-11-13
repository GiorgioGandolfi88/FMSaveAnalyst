"""Write fmsave tables into a career database, merging with what earlier imports stored.

Every record type has a physical table named like the type (`Player`, `LeagueTableRow`, ...)
holding the CURRENT state. What earlier imports stored and later changed is moved, never lost:

- ENTITY / SNAPSHOT readers: replaced versions and older snapshots go to `<Type>_history`
  (same columns, plus `_valid_to` = the import that replaced them on top-level tables);
  the view `<Type>_all` is current + history together;
- EVENT readers accumulate in the table itself across imports (a save only keeps a window);
- LATEST readers keep only the last import.

Tables of nested records (`Attributes`, `LeagueTableRow`, ...) carry `_parent_table`,
`_parent_field`, `_parent_rid` (the `_rid` of the record that holds them) and `_ord` (position
in the parent's list).
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
    Kind.ENTITY: [("_key", "INTEGER"), ("_hash", "INTEGER"), ("_valid_from", "INTEGER")],
    Kind.EVENT: [("_key", "INTEGER"), ("_hash", "INTEGER"), ("_first_seen", "INTEGER"),
                 ("_last_seen", "INTEGER")],
    Kind.SNAPSHOT: [("_import_id", "INTEGER")],
    Kind.LATEST: [("_import_id", "INTEGER")],
}  # fmt: skip
CHILD_META: list[tuple[str, str]] = [
    ("_parent_table", "TEXT"), ("_parent_field", "TEXT"), ("_parent_rid", "INTEGER"),
    ("_ord", "INTEGER"),
]  # fmt: skip
HISTORY_KINDS = frozenset({Kind.ENTITY, Kind.SNAPSHOT})
# Columns dashboards and typical queries filter on.
FILTER_COLUMNS = frozenset(
    {"club_uid", "player_uid", "competition_id", "season_year", "home_club_uid", "away_club_uid",
     "team_id"}
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

    def __init__(
        self,
        conn: sqlite3.Connection,
        spec: ReaderSpec,
        record_type: type,
        skip_groups: frozenset[type] = frozenset(),
    ) -> None:
        self.conn = conn
        self.spec = spec
        self.layout = build_layout(record_type, skip_groups)
        self.history = spec.kind in HISTORY_KINDS
        self.row_makers: dict[str, Callable[[Iterable[Any]], Iterator[tuple[Any, ...]]]] = {}
        for layout in self.layout.walk():
            self.row_makers.setdefault(layout.table, make_rows(layout))
        names = self.layout.column_names
        missing = [k for k in spec.key if k not in names]
        if missing:
            raise ValueError(f"{spec.name}: key columns {missing} are not columns of {names[:5]}")
        self.key_idx = [names.index(k) for k in spec.key]
        self.next_rid: dict[str, int] = {}
        self.buffers: dict[str, list[tuple[Any, ...]]] = {}
        # per destination table (in first-seen order): records read / rows written
        self.read_counts: dict[str, int] = {}
        self.insert_counts: dict[str, int] = {}
        self.parents: dict[str, set[str]] = {}
        for layout in self.layout.walk():
            self.read_counts.setdefault(layout.table, 0)
            self.insert_counts.setdefault(layout.table, 0)
            self.parents.setdefault(layout.table, set())
            for child in layout.children:
                self.parents.setdefault(child.layout.table, set()).add(layout.table)

    @property
    def tables(self) -> list[str]:
        return list(self.read_counts)

    def layouts(self) -> dict[str, Layout]:
        """One layout per table (a type reached through several fields appears once)."""
        out: dict[str, Layout] = {}
        for layout in self.layout.walk():
            out.setdefault(layout.table, layout)
        return out

    # ------------------------------------------------------------------ DDL

    def _meta(self, layout: Layout) -> list[tuple[str, str]]:
        return TOP_META[self.spec.kind] if layout is self.layout else CHILD_META

    def ensure_tables(self) -> None:
        for table, layout in self.layouts().items():
            cols = [("_rid", "INTEGER PRIMARY KEY"), *self._meta(layout),
                    *((c.name, c.sql_type) for c in layout.columns)]  # fmt: skip
            top = layout is self.layout
            self._ensure(table, cols, top)
            if self.history:
                extra = [("_valid_to", "INTEGER")] if top else []
                self._ensure(history_table(table), [*cols, *extra], top)
            self.next_rid[table] = self._max_rid(table) + 1

    def _ensure(self, table: str, cols: list[tuple[str, str]], top: bool) -> None:
        existing = {r[1] for r in self.conn.execute(f"PRAGMA table_info({q(table)})")}
        if not existing:
            ddl = ", ".join(f"{q(n)} {t}".rstrip() for n, t in cols)
            self.conn.execute(f"CREATE TABLE {q(table)} ({ddl})")
        else:
            for n, t in cols:
                if n not in existing:
                    self.conn.execute(f"ALTER TABLE {q(table)} ADD COLUMN {q(n)} {t}".rstrip())
        names = {n for n, _ in cols}
        if not top:
            self._index(table, ["_parent_rid", "_parent_table"])
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
        """`<Type>_all` = current rows + history (for readers that keep history)."""
        if not self.history:
            return []
        made = []
        for table, layout in self.layouts().items():
            cols = ", ".join(q(c) for c in self._columns(table))
            current = f"SELECT {cols}" + (", NULL AS _valid_to" if layout is self.layout else "")
            past = f"SELECT {cols}" + (", _valid_to" if layout is self.layout else "")
            view = all_view(table)
            self.conn.execute(f"DROP VIEW IF EXISTS {q(view)}")
            self.conn.execute(
                f"CREATE VIEW {q(view)} AS {current} FROM {q(table)} "
                f"UNION ALL {past} FROM {q(history_table(table))}"
            )
            made.append(view)
        return made

    # ------------------------------------------------------------------ data

    def _trees(self, layout: Layout, records: Sequence[Any]) -> Iterator[Tree]:
        table = layout.table
        self.read_counts[table] += len(records)
        rows = self.row_makers[table](records)
        children = layout.children
        for record, row in zip(records, rows, strict=True):
            if children:
                kids = tuple(
                    tuple(self._trees(child.layout, child_records(record, child)))
                    for child in children
                )
            else:
                kids = ()
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

    def _insert(self, tree: Tree, meta: tuple[Any, ...]) -> int:
        table = self.layout.table
        rid = self.next_rid[table]
        self.next_rid[table] = rid + 1
        self._push(table, (rid, *meta, *tree[0]))
        self._insert_children(self.layout, rid, tree)
        return rid

    def _insert_children(self, layout: Layout, parent_rid: int, tree: Tree) -> None:
        for child, subtrees in zip(layout.children, tree[1], strict=True):
            table = child.layout.table
            for ordinal, sub in enumerate(subtrees):
                rid = self.next_rid[table]
                self.next_rid[table] = rid + 1
                self._push(table, (rid, layout.table, child.field, parent_rid, ordinal, *sub[0]))
                self._insert_children(child.layout, rid, sub)

    def _descendants(self, layout: Layout, rids: list[int]) -> Iterator[tuple[Layout, list[int]]]:
        """(layout, rids) for every child table row below `rids` of `layout`, deepest first."""
        for child in layout.children:
            table = child.layout.table
            found: list[int] = []
            for start in range(0, len(rids), CHUNK):
                chunk = rids[start : start + CHUNK]
                marks = ", ".join("?" * len(chunk))
                found += [
                    r[0]
                    for r in self.conn.execute(
                        f"SELECT _rid FROM {q(table)} WHERE _parent_table = ? "
                        f"AND _parent_field = ? AND _parent_rid IN ({marks})",
                        (layout.table, child.field, *chunk),
                    )
                ]
            if found:
                yield from self._descendants(child.layout, found)
                yield (child.layout, found)

    def _remove(self, rids: list[int], valid_to: int | None, keep: bool) -> None:
        """Delete top-level rows and their descendants; with `keep`, copy them to history."""
        targets = [*self._descendants(self.layout, rids), (self.layout, rids)]
        for layout, ids in targets:
            table = layout.table
            cols = ", ".join(q(c) for c in self._columns(table))
            top = layout is self.layout
            for start in range(0, len(ids), CHUNK):
                chunk = ids[start : start + CHUNK]
                marks = ", ".join("?" * len(chunk))
                if keep:
                    if top:
                        self.conn.execute(
                            f"INSERT INTO {q(history_table(table))} ({cols}, _valid_to) "
                            f"SELECT {cols}, ? FROM {q(table)} WHERE _rid IN ({marks})",
                            (valid_to, *chunk),
                        )
                    else:
                        self.conn.execute(
                            f"INSERT INTO {q(history_table(table))} ({cols}) "
                            f"SELECT {cols} FROM {q(table)} WHERE _rid IN ({marks})",
                            chunk,
                        )
                self.conn.execute(f"DELETE FROM {q(table)} WHERE _rid IN ({marks})", chunk)

    def merge(self, records: Sequence[Any], import_id: int) -> MergeStats:
        self.ensure_tables()
        kind = self.spec.kind
        stats = MergeStats()
        top = q(self.layout.table)
        if kind in (Kind.SNAPSHOT, Kind.LATEST):
            old = [r[0] for r in self.conn.execute(f"SELECT _rid FROM {top}")]
            if old:
                self._remove(old, import_id, keep=kind is Kind.SNAPSHOT)
            stats.closed = len(old) if kind is Kind.SNAPSHOT else 0
            for tree in self._trees(self.layout, records):
                self._insert(tree, (import_id,))
                stats.rows += 1
            stats.inserted = stats.rows
            self.flush_all()
            return stats

        if kind is Kind.ENTITY:
            sql = f"SELECT _key, _rid, _hash, _valid_from FROM {top}"
        else:
            sql = f"SELECT _key, _rid, _hash, _first_seen FROM {top}"
        existing: dict[int, tuple[int, int, int]] = {
            k: (rid, h, first) for k, rid, h, first in self.conn.execute(sql)
        }
        seen: set[int] = set()
        occurrences: dict[Any, int] = {}
        touched: list[tuple[int, int]] = []  # (import_id, rid) for EVENT last_seen
        replaced: list[int] = []

        for tree in self._trees(self.layout, records):
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
                first = import_id if kind is Kind.ENTITY else old[2]
            if kind is Kind.ENTITY:
                self._insert(tree, (key, row_hash, first))
            else:
                self._insert(tree, (key, row_hash, first, import_id))

        self.flush_all()
        if kind is Kind.ENTITY:
            gone = [v[0] for k, v in existing.items() if k not in seen]
            stats.closed = len(gone)
            if replaced or gone:
                self._remove(replaced + gone, import_id, keep=True)
        elif replaced:
            self._remove(replaced, None, keep=False)
        if touched:
            self.conn.executemany(f"UPDATE {top} SET _last_seen = ? WHERE _rid = ?", touched)
        return stats
