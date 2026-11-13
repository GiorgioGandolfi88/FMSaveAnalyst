"""Logical relations between career tables, used to suggest joins in the query builder.

SQLite has no foreign keys here (the importer writes plain tables), so relations are derived from
column naming conventions of fmsave and from the importer's catalog (`_tables.parent_table`),
and checked against the objects that actually exist.

A child table joins its parent on `_import_id` plus every idx key of the parent
(`league_tables_rows_matches` -> `league_tables_rows` on `_import_id`, `league_tables_idx`,
`rows_idx`): the relation names the parent's own key and lists the other conditions in `also`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Relation:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    also: tuple[tuple[str, str], ...] = field(default=())  # extra (from, to) column pairs

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_table": self.from_table,
            "from_column": self.from_column,
            "to_table": self.to_table,
            "to_column": self.to_column,
            "also": [list(p) for p in self.also],
        }


# column name (exact) -> target (table, column); tables are named like the fmsave readers
EXACT: dict[str, tuple[str, str]] = {
    "player_uid": ("players", "uid"),
    "person_uid": ("staff", "uid"),
    "manager_staff_uid": ("staff", "uid"),
    "nation_id": ("nations", "nation_id"),
    "fa_nation_id": ("nations", "nation_id"),
    "club_nation_id": ("nations", "nation_id"),
    "club_fa_nation_id": ("nations", "nation_id"),
    "competition_id": ("competitions", "id"),
    "stage_id": ("stages", "id"),
    "previous_stage_id": ("stages", "id"),
    "stadium_uid": ("stadiums", "uid"),
    "referee_id": ("officials", "referee_id"),
    "type_id": ("injury_types", "id"),
    "city_id": ("ref_cities", "database_id"),
}
# per-table overrides: (table, column) -> target
SPECIFIC: dict[tuple[str, str], tuple[str, str]] = {
    ("competitions", "database_id"): ("ref_competitions", "database_id"),
    ("nations", "database_id"): ("ref_nations", "database_id"),
}


def _target(table: str, column: str) -> tuple[str, str] | None:
    if (table, column) in SPECIFIC:
        return SPECIFIC[(table, column)]
    if column in EXACT:
        return EXACT[column]
    if column.endswith("club_uid"):
        return ("clubs", "uid")
    if column.endswith("team_id"):
        return ("clubs_teams", "team_id")
    return None


def derive_relations(objects: Iterable[dict[str, Any]]) -> list[Relation]:
    """`objects` as returned by describe_schema (name, logical, parent, columns)."""
    objs = list(objects)
    columns = {o["name"]: [c["name"] for c in o["columns"]] for o in objs}
    relations: list[Relation] = []
    for o in objs:
        name = o["name"]
        logical = o.get("logical") or name
        suffix = name[len(logical) :]  # "", "_all" or "_history"
        cols = columns[name]
        parent = o.get("parent")
        if parent:
            # a nested record and its parent; history rows point to history parents
            to_table = f"{parent}{suffix}"
            parent_cols = set(columns.get(to_table, ()))
            parent_keys = [c for c in columns.get(to_table, ()) if c.endswith("_idx")]
            keys = [c for c in parent_keys if c in cols]
            if keys and "_import_id" in parent_cols and len(keys) == len(parent_keys):
                own = keys[-1]
                also = (("_import_id", "_import_id"), *((k, k) for k in keys[:-1]))
                relations.append(Relation(name, own, to_table, own, also))
        for col in cols:
            target = _target(logical, col)
            if target is None:
                continue
            to_table, to_column = target
            if to_table == logical and to_column == col:
                continue  # the key column of the target itself
            if to_column in columns.get(to_table, ()):
                relations.append(Relation(name, col, to_table, to_column))
    return relations
