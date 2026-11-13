"""Which stored columns are hidden ("spoiler" data the game does not show the player).

Rules are expressed on fmsave field paths (`_columns.source_path`), so they apply to every table
that stores the field (players, staff, their history tables) and keep working when fmsave adds
columns. Masked columns read as NULL everywhere: grids, hand-written SQL (also inside WHERE,
ORDER BY, JOINs and aggregates), dashboards and data sent to AI assistants.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from fmsa.config import MaskingSettings

POTENTIAL = frozenset({"ability.potential", "ability.potential_range_code"})
CURRENT = frozenset({"ability.current"})
HIDDEN_ATTRIBUTES = frozenset(
    f"attributes.{a}"
    for a in ("consistency", "dirtiness", "important_matches", "injury_proneness", "versatility")
)
PERSONALITY_PREFIX = "personality."

# Internal row hashes change whenever any value changes, hidden ones included.
ALWAYS_HIDDEN_COLUMNS = frozenset({"_hash", "_key"})


@dataclass(frozen=True, slots=True)
class MaskRules:
    paths: frozenset[str]
    path_prefixes: tuple[str, ...]
    extra: frozenset[tuple[str, str]]  # (table or view name, column), lower-case

    @classmethod
    def from_settings(cls, s: MaskingSettings) -> MaskRules:
        paths: set[str] = set()
        prefixes: list[str] = []
        if s.potential_ability:
            paths |= POTENTIAL
        if s.current_ability:
            paths |= CURRENT
        if s.hidden_attributes:
            paths |= HIDDEN_ATTRIBUTES
        if s.personality:
            prefixes.append(PERSONALITY_PREFIX)
        extra: set[tuple[str, str]] = set()
        for item in s.extra_columns:
            table, _, column = item.strip().partition(".")
            if table and column:
                extra.add((table.lower(), column.lower()))
        return cls(frozenset(paths), tuple(prefixes), frozenset(extra))

    def matches(self, path: str) -> bool:
        # paths are "<table>.<field path>" (players.ability.potential,
        # players.raw_attributes.consistency): match the rule on the trailing part of the path
        path = path.lower()
        if any(path == p or path.endswith("." + p) or path.endswith("_" + p) for p in self.paths):
            return True
        return any(path.startswith(p) or f".{p}" in path for p in self.path_prefixes)


def masked_columns(conn: sqlite3.Connection, rules: MaskRules) -> set[tuple[str, str]]:
    """(table, column) pairs to hide, for base tables and their views (lower-case names)."""
    hidden: set[tuple[str, str]] = set()
    try:
        rows = conn.execute("SELECT table_name, column_name, source_path FROM _columns").fetchall()
    except sqlite3.OperationalError:
        rows = []
    for table, column, path in rows:
        if rules.matches(path or ""):
            for name in (table, f"{table}_all", f"{table}_history"):
                hidden.add((name.lower(), column.lower()))
    tables = {t.lower() for t, _, _ in rows}
    for table, column in rules.extra:
        base = table
        for suffix in ("_all", "_history"):
            if table.endswith(suffix) and table.removesuffix(suffix) in tables:
                base = table.removesuffix(suffix)
        for name in (base, f"{base}_all", f"{base}_history"):
            hidden.add((name, column))
    return hidden
