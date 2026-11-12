"""Logical relations between career tables, used to suggest joins in the query builder.

SQLite has no foreign keys here (the importer writes plain tables), so relations are derived from
column naming conventions of fmsave and checked against the objects that actually exist.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Relation:
    from_table: str
    from_column: str
    to_table: str
    to_column: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


# column name (exact) -> target (table, column)
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
    "city_id": ("ref_cities", "database_id"),
}
# per-table overrides: (table, column) -> target
SPECIFIC: dict[tuple[str, str], tuple[str, str]] = {
    ("injuries", "type_id"): ("injury_types", "id"),
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
        return ("clubs__teams", "team_id")
    return None


def derive_relations(objects: Iterable[dict[str, Any]]) -> list[Relation]:
    """`objects` as returned by describe_schema (name, group, parent, columns)."""
    objs = list(objects)
    columns = {o["name"]: {c["name"] for c in o["columns"]} for o in objs}
    relations: list[Relation] = []
    for o in objs:
        name = o["name"]
        logical = name.removesuffix("_all") if o["group"] == "history" else name
        for col in columns[name]:
            if col == "_parent_rid" and o.get("parent"):
                parent = o["parent"]
                target = (f"{parent}_all", "_rid") if o["group"] == "history" else (parent, "_rid")
            else:
                target = _target(logical, col)
            if target is None:
                continue
            to_table, to_column = target
            if to_table == logical and to_column == col:
                continue  # the key column of the target itself
            if to_column in columns.get(to_table, set()):
                relations.append(Relation(name, col, to_table, to_column))
    return relations
