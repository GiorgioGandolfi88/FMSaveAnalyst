"""Turn fmsave record types into flat SQLite table layouts.

The layout is derived from the dataclass *types* (not from data), so a table always has the same
columns whatever the save contains:

- nested records (`player.ability.current`) become columns joined with "_" (`ability_current`);
- `CodedValue` fields become `<name>_label` / `<name>_raw` (that is just the nested-record rule);
- tuples of records become child tables (`players__traits`) linked by `_parent_rid`;
- tuples of scalars and mappings become JSON text columns;
- dates and times are ISO text, enums their name, booleans 0/1.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import json
import types
import typing
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import fmsave

# Raw, undecoded value bags: never useful to users and large.
GLOBAL_EXCLUDE = frozenset({"unknown"})

SqlType = str  # "INTEGER" | "REAL" | "TEXT"


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    sql_type: SqlType
    path: tuple[str, ...]  # attribute path from the record
    status: str  # fmsave field status of the leaf field ("verified", "unconfirmed", ...)
    convert: Callable[[Any], Any]


@dataclass(slots=True)
class Layout:
    """Columns and child tables of one record type (as stored under one table name)."""

    table: str
    record_type: type
    columns: list[Column] = field(default_factory=list)
    children: list[tuple[tuple[str, ...], Layout]] = field(default_factory=list)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


# ---------------------------------------------------------------------------- conversions


def _conv_identity(v: Any) -> Any:
    return v


def _conv_bool(v: Any) -> Any:
    return None if v is None else int(v)


def _conv_float(v: Any) -> Any:
    return None if v is None else float(v)


def _conv_text(v: Any) -> Any:
    if v is None or isinstance(v, str):
        return v
    if isinstance(v, enum.Enum):
        return v.name
    if isinstance(v, (dt.date, dt.time, dt.datetime)):
        return v.isoformat()
    return str(v)


def _json_default(v: Any) -> Any:
    if isinstance(v, enum.Enum):
        return v.name
    if isinstance(v, (dt.date, dt.time, dt.datetime)):
        return v.isoformat()
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: getattr(v, f.name) for f in dataclasses.fields(v)}
    if isinstance(v, (set, frozenset)):
        return sorted(v, key=repr)
    if isinstance(v, Mapping):
        return dict(v)
    return repr(v)


def _conv_json(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, Mapping):
        v = {str(k): x for k, x in v.items()}
    elif isinstance(v, (set, frozenset)):
        v = sorted(v, key=repr)
    return json.dumps(v, default=_json_default, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------- type analysis


def _unwrap_optional(tp: Any) -> Any:
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return _unwrap_optional(args[0])
        return Any  # a real union: stored as text
    return tp


def _record_class(tp: Any) -> type | None:
    """The dataclass behind `tp` (also for generic aliases such as CodedValue[X])."""
    base = typing.get_origin(tp) or tp
    if isinstance(base, type) and dataclasses.is_dataclass(base):
        return base
    return None


def _sequence_item(tp: Any) -> Any | None:
    origin = typing.get_origin(tp)
    if origin in (tuple, list, Sequence, frozenset, set):
        args = [a for a in typing.get_args(tp) if a is not Ellipsis]
        return args[0] if args else Any
    return None


def _scalar(tp: Any) -> tuple[SqlType, Callable[[Any], Any]]:
    if tp is bool:
        return "INTEGER", _conv_bool
    if tp is int:
        return "INTEGER", _conv_identity
    if tp is float:
        return "REAL", _conv_float
    if isinstance(tp, type) and issubclass(tp, enum.IntEnum):
        return "TEXT", _conv_text  # keep the readable name; raw codes come in *_raw columns
    return "TEXT", _conv_text


def _status(cls: type, name: str) -> str:
    try:
        return str(fmsave.field_status(cls, name)).rsplit(".", 1)[-1].lower()
    except Exception:
        return ""


def _hints(cls: type) -> dict[str, Any]:
    try:
        return typing.get_type_hints(cls)
    except Exception:
        return {f.name: f.type for f in dataclasses.fields(cls)}


def build_layout(
    table: str,
    record_type: type,
    exclude: frozenset[str] = frozenset(),
) -> Layout:
    layout = Layout(table=table, record_type=record_type)
    _walk(layout, record_type, (), "", exclude, depth=0)
    return layout


def _walk(
    layout: Layout,
    cls: type,
    path: tuple[str, ...],
    prefix: str,
    exclude: frozenset[str],
    depth: int,
) -> None:
    hints = _hints(cls)
    for f in dataclasses.fields(cls):
        if f.name in GLOBAL_EXCLUDE or (depth == 0 and f.name in exclude):
            continue
        tp = _unwrap_optional(hints.get(f.name, Any))
        fpath = (*path, f.name)
        name = f"{prefix}{f.name}"
        nested = _record_class(tp)
        if nested is not None and depth < 4:
            _walk(layout, nested, fpath, name + "_", frozenset(), depth + 1)
            continue
        item = _sequence_item(tp)
        if item is not None:
            item_cls = _record_class(_unwrap_optional(item))
            if item_cls is not None:
                child = Layout(table=f"{layout.table}__{name}", record_type=item_cls)
                _walk(child, item_cls, (), "", frozenset(), 0)
                layout.children.append((fpath, child))
                continue
            layout.columns.append(Column(name, "TEXT", fpath, _status(cls, f.name), _conv_json))
            continue
        if typing.get_origin(tp) in (dict, Mapping) or tp in (dict, Mapping):
            layout.columns.append(Column(name, "TEXT", fpath, _status(cls, f.name), _conv_json))
            continue
        sql_type, conv = _scalar(tp)
        layout.columns.append(Column(name, sql_type, fpath, _status(cls, f.name), conv))


# ---------------------------------------------------------------------------- flattening


def _get(record: Any, path: tuple[str, ...]) -> Any:
    v = record
    for p in path:
        if v is None:
            return None
        v = getattr(v, p, None)
    return v


def make_flattener(layout: Layout) -> Callable[[Any], tuple[Any, ...]]:
    """A fast function record -> tuple of column values (children not included)."""
    getters: list[Callable[[Any], Any]] = []
    for col in layout.columns:
        conv = col.convert
        if len(col.path) == 1:
            attr = col.path[0]
            if conv is _conv_identity:
                getters.append(lambda r, a=attr: getattr(r, a, None))
            else:
                getters.append(lambda r, a=attr, c=conv: c(getattr(r, a, None)))
        else:
            getters.append(lambda r, p=col.path, c=conv: c(_get(r, p)))

    def flatten(record: Any) -> tuple[Any, ...]:
        return tuple(g(record) for g in getters)

    return flatten


def child_records(record: Any, path: tuple[str, ...]) -> Sequence[Any]:
    v = _get(record, path)
    return v if v else ()
