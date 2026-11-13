"""Turn fmsave record types into SQLite tables: one table per record type, named like the type.

Columns are exactly `fmsave.export.column_names(<type>)`, in the same order, and values come from
`fmsave.export.flat_rows(..., json_ready=True)`: the same flat rows `Table.to_pandas()` gives.

- groups (`Player.attributes`) are flattened into prefixed columns (`attributes_crossing`), as
  fmsave does; each group is ALSO stored as a row of its own type's table (`Attributes`);
- coded values become `<name>` (label) and `<name>_code` (raw number), as fmsave does;
- tuples of records (`LeagueTable.rows`) stay a JSON column, as fmsave does, and every item is
  ALSO stored as a row of its own type's table (`LeagueTableRow`), linked to its parent;
- other tuples and mappings become JSON text, dates ISO text, booleans 0/1.

A group whose type is read by a reader of its own (`Player.contract` -> `Contract`, read by
`Save.contracts()`) is not stored twice: its columns stay in the parent only.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import json
import types
import typing
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import fmsave
import fmsave.export as fexport

SqlType = str  # "INTEGER" | "REAL" | "TEXT" | "" (no affinity)


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    sql_type: SqlType
    path: tuple[str, ...]  # field path inside the record (for masking and documentation)
    status: str  # fmsave field status ("verified", "unconfirmed", "computed", ...)


@dataclass(frozen=True, slots=True)
class Child:
    """A field of a record stored as rows of another type's table."""

    field: str
    kind: str  # "list" (tuple of records) | "group" (one record)
    layout: Layout


@dataclass(slots=True)
class Layout:
    table: str  # = the record type's name
    record_type: type
    columns: list[Column] = dataclasses.field(default_factory=list)
    children: list[Child] = field(default_factory=list)
    exact: bool = True  # columns come from fmsave.export (False: fallback flattening)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def walk(self) -> Iterator[Layout]:
        """This layout and every descendant (a type reached twice is yielded twice)."""
        yield self
        for child in self.children:
            yield from child.layout.walk()


# ---------------------------------------------------------------------------- type analysis


def _unwrap_optional(tp: Any) -> Any:
    if typing.get_origin(tp) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        return _unwrap_optional(args[0]) if len(args) == 1 else Any
    return tp


def _record_class(tp: Any) -> type | None:
    base = typing.get_origin(tp) or tp
    if isinstance(base, type) and dataclasses.is_dataclass(base):
        return base
    return None


def _is_coded(cls: type | None) -> bool:
    return cls is not None and cls is getattr(fmsave, "CodedValue", None)


def _tuple_item(tp: Any) -> Any | None:
    if typing.get_origin(tp) in (tuple, list, Sequence):
        args = [a for a in typing.get_args(tp) if a is not Ellipsis]
        return args[0] if args else Any
    return None


def _hints(cls: type) -> dict[str, Any]:
    try:
        return typing.get_type_hints(cls)
    except Exception:
        return {f.name: f.type for f in dataclasses.fields(cls)}


def _status(cls: type, name: str) -> str:
    try:
        return str(fmsave.field_status(cls, name)).rsplit(".", 1)[-1].lower()
    except Exception:
        return ""


def _scalar_sql(tp: Any) -> SqlType:
    if tp is bool or tp is int or (isinstance(tp, type) and issubclass(tp, enum.IntEnum)):
        return "INTEGER"
    if tp is float:
        return "REAL"
    if tp in (str, dt.date, dt.datetime, dt.time) or (
        isinstance(tp, type) and issubclass(tp, enum.Enum)
    ):
        return "TEXT"
    return ""


def _describe(cls: type, prefix: str = "", path: tuple[str, ...] = ()) -> dict[str, Column]:
    """Our own description of the flat columns of `cls` (types, paths, statuses), keyed by the
    column name fmsave uses. Only used to type and document fmsave's columns."""
    out: dict[str, Column] = {}
    hints = _hints(cls)
    for f in dataclasses.fields(cls):
        tp = _unwrap_optional(hints.get(f.name, Any))
        name, fpath, status = f"{prefix}{f.name}", (*path, f.name), _status(cls, f.name)
        rec = _record_class(tp)
        if _is_coded(rec):
            out[name] = Column(name, "TEXT", fpath, status)
            out[f"{name}_code"] = Column(f"{name}_code", "INTEGER", fpath, status)
        elif rec is not None:
            out.update(_describe(rec, f"{name}_", fpath))
        else:
            item = _tuple_item(tp)
            if item is not None or isinstance(tp, type) and issubclass(tp, Mapping):
                out[name] = Column(name, "TEXT", fpath, status)
                if item is not None and _is_coded(_record_class(_unwrap_optional(item))):
                    out[f"{name}_code"] = Column(f"{name}_code", "TEXT", fpath, status)
            elif typing.get_origin(tp) in (dict, Mapping) or f.name == "unknown":
                out[name] = Column(name, "TEXT", fpath, status)
                for key in getattr(cls, "UNKNOWN_KEYS", ()) or ():
                    k = f"{name}_{key}"
                    out[k] = Column(k, "", (*fpath, str(key)), status)
            else:
                out[name] = Column(name, _scalar_sql(tp), fpath, status)
    for name in _computed(cls):
        out[f"{prefix}{name}"] = Column(f"{prefix}{name}", "REAL", (*path, name), "computed")
    return out


def _computed(cls: type) -> tuple[str, ...]:
    try:
        return tuple(fexport.computed_field_names(cls))
    except Exception:
        return ()


def build_layout(record_type: type, skip_groups: frozenset[type] = frozenset()) -> Layout:
    """Layout of `record_type` and of the record types stored in tables of their own.

    `skip_groups`: group types not to store as rows of their own (read by another reader).
    """
    layout = Layout(table=record_type.__name__, record_type=record_type)
    described = _describe(record_type)
    try:
        names = fexport.column_names(record_type)
    except (TypeError, ValueError):
        # a type fmsave.export does not support (e.g. the experimental Fm27Span): store the
        # top-level fields, nested values as JSON
        layout.exact = False
        hints = _hints(record_type)
        for f in dataclasses.fields(record_type):
            tp = _unwrap_optional(hints.get(f.name, Any))
            layout.columns.append(
                Column(f.name, _scalar_sql(tp), (f.name,), _status(record_type, f.name))
            )
        return layout
    for name in names:
        col = described.get(name) or Column(name, "", (name,), "")
        layout.columns.append(dataclasses.replace(col, name=name))

    hints = _hints(record_type)
    for f in dataclasses.fields(record_type):
        tp = _unwrap_optional(hints.get(f.name, Any))
        rec = _record_class(tp)
        if rec is not None and not _is_coded(rec):
            if rec not in skip_groups:
                layout.children.append(Child(f.name, "group", build_layout(rec, skip_groups)))
            continue
        item = _tuple_item(tp)
        item_rec = _record_class(_unwrap_optional(item)) if item is not None else None
        if item_rec is not None and not _is_coded(item_rec):
            layout.children.append(Child(f.name, "list", build_layout(item_rec, skip_groups)))
    return layout


# ---------------------------------------------------------------------------- values


def _json_default(v: Any) -> Any:
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (dt.date, dt.time, dt.datetime)):
        return v.isoformat()
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: getattr(v, f.name) for f in dataclasses.fields(v)}
    if isinstance(v, (set, frozenset)):
        return sorted(v, key=repr)
    if isinstance(v, Mapping):
        return {str(k): x for k, x in v.items()}
    return repr(v)


def _to_json(v: Any) -> str:
    if isinstance(v, Mapping):
        v = {str(k): x for k, x in v.items()}
    return json.dumps(v, default=_json_default, ensure_ascii=False, separators=(",", ":"))


_I64 = 2**63


def sql_value(v: Any) -> Any:
    t = type(v)
    if v is None or t is str or t is float:
        return v
    if t is int:
        return v if -_I64 <= v < _I64 else str(v)  # SQLite integers are 64-bit
    if t is bool:
        return int(v)
    if isinstance(v, (list, tuple, Mapping, set, frozenset)):
        return _to_json(v)
    if isinstance(v, enum.Enum):
        return v.value if isinstance(v.value, (int, str, float)) else v.name
    if isinstance(v, int):
        return int(v) if -_I64 <= v < _I64 else str(v)
    if isinstance(v, (float, str)):
        return v
    if isinstance(v, (dt.date, dt.time, dt.datetime)):
        return v.isoformat()
    if dataclasses.is_dataclass(v):
        return _to_json(v)
    return str(v)


def make_rows(layout: Layout) -> Callable[[Iterable[Any]], Iterator[tuple[Any, ...]]]:
    """records -> flat rows (tuples, in column order) ready for SQLite."""
    if not layout.exact:
        attrs = layout.column_names

        def fallback(records: Iterable[Any]) -> Iterator[tuple[Any, ...]]:
            for r in records:
                yield tuple(sql_value(getattr(r, a, None)) for a in attrs)

        return fallback

    record_type = layout.record_type

    def rows(records: Iterable[Any]) -> Iterator[tuple[Any, ...]]:
        for row in fexport.flat_rows(records, record_type, json_ready=True):
            yield tuple(map(sql_value, row.values()))

    return rows


def child_records(record: Any, child: Child) -> Sequence[Any]:
    v = getattr(record, child.field, None)
    if v is None:
        return ()
    return (v,) if child.kind == "group" else v
