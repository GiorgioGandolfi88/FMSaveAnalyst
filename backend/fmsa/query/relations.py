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


# column name (exact) -> target (table, column); tables are named like the fmsave record types
EXACT: dict[str, tuple[str, str]] = {
    "player_uid": ("Player", "uid"),
    "person_uid": ("Staff", "uid"),
    "manager_staff_uid": ("Staff", "uid"),
    "nation_id": ("Nation", "nation_id"),
    "fa_nation_id": ("Nation", "nation_id"),
    "club_nation_id": ("Nation", "nation_id"),
    "club_fa_nation_id": ("Nation", "nation_id"),
    "competition_id": ("Competition", "id"),
    "stage_id": ("Stage", "id"),
    "previous_stage_id": ("Stage", "id"),
    "stadium_uid": ("Stadium", "uid"),
    "referee_id": ("Official", "referee_id"),
    "type_id": ("InjuryType", "id"),
    "city_id": ("ref_cities", "database_id"),
}
# per-table overrides: (table, column) -> target
SPECIFIC: dict[tuple[str, str], tuple[str, str]] = {
    ("Competition", "database_id"): ("ref_competitions", "database_id"),
    ("Nation", "database_id"): ("ref_nations", "database_id"),
}
SUFFIXES = ("_all", "_history")


def _target(table: str, column: str) -> tuple[str, str] | None:
    if (table, column) in SPECIFIC:
        return SPECIFIC[(table, column)]
    if column in EXACT:
        return EXACT[column]
    if column.endswith("club_uid"):
        return ("Club", "uid")
    if column.endswith("team_id"):
        return ("Team", "team_id")
    return None


def _logical(name: str) -> str:
    for suffix in SUFFIXES:
        if name.endswith(suffix):
            return name.removesuffix(suffix)
    return name


def derive_relations(objects: Iterable[dict[str, Any]]) -> list[Relation]:
    """`objects` as returned by describe_schema (name, group, parent, columns)."""
    objs = list(objects)
    columns = {o["name"]: {c["name"] for c in o["columns"]} for o in objs}
    relations: list[Relation] = []
    for o in objs:
        name = o["name"]
        logical = _logical(name)
        suffix = name[len(logical) :]
        for col in columns[name]:
            targets: list[tuple[str, str]] = []
            if col == "_parent_rid" and o.get("parent"):
                # a nested record's parent; history rows point to history parents
                targets = [(f"{p}{suffix}", "_rid") for p in str(o["parent"]).split(",")]
            else:
                target = _target(logical, col)
                if target is not None:
                    targets = [target]
            for to_table, to_column in targets:
                if to_table == logical and to_column == col:
                    continue  # the key column of the target itself
                if to_column in columns.get(to_table, set()):
                    relations.append(Relation(name, col, to_table, to_column))
    return relations
