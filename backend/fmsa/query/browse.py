"""Translate a grid request (AG Grid filter and sort models) into a safe SELECT.

Identifiers are only ever taken from the career schema (never from the request as raw SQL), and
all values are bound parameters.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fmsa.db import q


class BrowseError(ValueError):
    pass


TEXT_OPS = {
    "contains": ("instr(lower({c}), lower(?)) > 0", lambda v: v),
    "notContains": ("({c} IS NULL OR instr(lower({c}), lower(?)) = 0)", lambda v: v),
    "equals": ("lower({c}) = lower(?)", lambda v: v),
    "notEqual": ("({c} IS NULL OR lower({c}) != lower(?))", lambda v: v),
    "startsWith": ("lower({c}) LIKE lower(?) ESCAPE '\\'", lambda v: _like(v) + "%"),
    "endsWith": ("lower({c}) LIKE lower(?) ESCAPE '\\'", lambda v: "%" + _like(v)),
}
CMP_OPS = {
    "equals": "=",
    "notEqual": "!=",
    "lessThan": "<",
    "lessThanOrEqual": "<=",
    "greaterThan": ">",
    "greaterThanOrEqual": ">=",
}


def _like(v: str) -> str:
    return v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _date(v: Any) -> Any:
    # AG Grid sends "YYYY-MM-DD hh:mm:ss"; stored dates are "YYYY-MM-DD"
    return str(v)[:10] if v is not None else None


def _condition(column: str, cond: Mapping[str, Any], params: list[Any]) -> str:
    c = q(column)
    if "conditions" in cond:  # combined model: {operator, conditions: [...]}
        joiner = " OR " if str(cond.get("operator", "AND")).upper() == "OR" else " AND "
        parts = [_condition(column, sub, params) for sub in cond["conditions"]]
        return "(" + joiner.join(parts) + ")"
    kind = cond.get("filterType")
    op = cond.get("type")
    if op == "blank":
        return f"({c} IS NULL OR {c} = '')"
    if op == "notBlank":
        return f"({c} IS NOT NULL AND {c} != '')"
    if kind == "text":
        if op not in TEXT_OPS:
            raise BrowseError(f"unsupported text filter {op}")
        template, conv = TEXT_OPS[op]
        params.append(conv(str(cond.get("filter", ""))))
        return template.format(c=c)
    if kind in ("number", "date"):
        key, to = ("filter", "filterTo") if kind == "number" else ("dateFrom", "dateTo")
        conv = (lambda v: v) if kind == "number" else _date
        if op == "inRange":
            params.extend([conv(cond.get(key)), conv(cond.get(to))])
            return f"({c} >= ? AND {c} <= ?)"
        if op not in CMP_OPS:
            raise BrowseError(f"unsupported {kind} filter {op}")
        params.append(conv(cond.get(key)))
        return f"{c} {CMP_OPS[op]} ?"
    raise BrowseError(f"unsupported filter type {kind}")


def build_browse_sql(
    table: str,
    available: Sequence[str],
    columns: Sequence[str] | None,
    filter_model: Mapping[str, Any] | None,
    sort_model: Sequence[Mapping[str, Any]] | None,
) -> tuple[str, str, list[Any]]:
    """Returns (select_sql, count_sql, params) — without LIMIT/OFFSET."""
    known = set(available)
    cols = [c for c in (columns or available) if c in known]
    if not cols:
        raise BrowseError("no columns selected")
    params: list[Any] = []
    where = []
    for col, cond in (filter_model or {}).items():
        if col not in known:
            raise BrowseError(f"unknown column {col}")
        where.append(_condition(col, cond, params))
    order = []
    for s in sort_model or []:
        col = s.get("colId")
        if col not in known:
            raise BrowseError(f"unknown column {col}")
        direction = "DESC" if str(s.get("sort", "asc")).lower() == "desc" else "ASC"
        order.append(f"{q(str(col))} {direction}")
    select = ", ".join(q(c) for c in cols)
    sql = f"SELECT {select} FROM {q(table)}"
    count = f"SELECT count(*) FROM {q(table)}"
    if where:
        clause = " WHERE " + " AND ".join(where)
        sql += clause
        count += clause
    if order:
        sql += " ORDER BY " + ", ".join(order)
    return sql, count, params
