"""Step 0 spike: compare consecutive saves of one career (identifier stability, overlap).

Usage:
    python spikes/compare_saves.py <out_dir> <stem1> <stem2> [<stem3> ...]

Reads <stem>.summary.json / <stem>.keys.json written by inspect_save.py and prints a markdown
report for every consecutive pair (stem1→stem2, stem2→stem3, ...).
"""

from __future__ import annotations

import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load(out_dir: Path, stem: str) -> tuple[dict[str, Any], dict[str, Any]]:
    s = json.loads((out_dir / f"{stem}.summary.json").read_text(encoding="utf-8"))
    k = json.loads((out_dir / f"{stem}.keys.json").read_text(encoding="utf-8"))
    return s, k


def rows(keys: dict[str, Any], reader: str, cols: list[str]) -> list[tuple[Any, ...]]:
    t = keys.get(reader) or {}
    if not t or any(c not in t for c in cols):
        return []
    return list(zip(*(t[c] for c in cols), strict=False))


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def identity(ka: dict, kb: dict, reader: str, idcol: str, attrs: list[str]) -> str:
    """How stable is `idcol` between saves: same id → same attributes?"""
    a = {r[0]: r[1:] for r in rows(ka, reader, [idcol, *attrs])}
    b = {r[0]: r[1:] for r in rows(kb, reader, [idcol, *attrs])}
    if not a or not b:
        return f"| {reader} | {idcol} | n/a | | | |"
    shared = a.keys() & b.keys()
    same = sum(1 for i in shared if a[i] == b[i])
    return (
        f"| {reader} | {idcol} → {', '.join(attrs)} | {len(a)} → {len(b)} | {len(shared)} "
        f"| {same} ({pct(same, len(shared))}) | {len(b.keys() - a.keys())} |"
    )


def reverse_identity(ka: dict, kb: dict, reader: str, natural: str, idcol: str) -> str:
    """For records with the same natural key (game database id), is the save id unchanged?"""
    a = Counter()
    ma = {}
    for nat, i in rows(ka, reader, [natural, idcol]):
        if nat is not None:
            a[nat] += 1
            ma[nat] = i
    mb = {}
    b = Counter()
    for nat, i in rows(kb, reader, [natural, idcol]):
        if nat is not None:
            b[nat] += 1
            mb[nat] = i
    uniq = [n for n in ma.keys() & mb.keys() if a[n] == 1 and b[n] == 1]
    same = sum(1 for n in uniq if ma[n] == mb[n])
    dup_a = sum(1 for n, c in a.items() if c > 1)
    return (
        f"| {reader} | {natural} → {idcol} | {len(uniq)} | {same} ({pct(same, len(uniq))}) "
        f"| dup {natural} in A: {dup_a} |"
    )


def overlap(
    ka: dict,
    kb: dict,
    reader: str,
    key: list[str],
    value: list[str],
    only: tuple[str, Any] | None = None,
) -> str:
    cols = key + value + ([only[0]] if only and only[0] not in key + value else [])
    ra = rows(ka, reader, cols)
    rb = rows(kb, reader, cols)
    if not ra:
        return f"| {reader} | {'+'.join(key)} | n/a | | | |"
    if only:
        idx = cols.index(only[0])
        ra = [r for r in ra if r[idx] == only[1]]
    nk = len(key)
    nv = len(value)
    a = {r[:nk]: r[nk : nk + nv] for r in ra}
    b = {r[:nk]: r[nk : nk + nv] for r in rb}
    dup_a = len(ra) - len(a)
    kept = a.keys() & b.keys()
    same = sum(1 for k in kept if a[k] == b[k])
    return (
        f"| {reader} | {'+'.join(key)} (= {', '.join(value)}) | {len(a)} (dup {dup_a}) "
        f"| {len(kept)} ({pct(len(kept), len(a))}) | {same} ({pct(same, len(kept))}) "
        f"| {len(b.keys() - a.keys())} |"
    )


def report(out_dir: Path, sa_stem: str, sb_stem: str) -> str:
    sa, ka = load(out_dir, sa_stem)
    sb, kb = load(out_dir, sb_stem)
    ia, ib = sa["info"], sb["info"]
    out = [f"## {sa['file']} → {sb['file']}", ""]
    out.append(
        f"- game_date: {ia['game_date']} → {ib['game_date']}; build: {ia['build']} → "
        f"{ib['build']}; db_version: {ia['db_version']} → {ib['db_version']}"
    )
    ss_a, ss_b = ia["summary_strings"], ib["summary_strings"]
    out.append(f"- summary_strings in common: {sorted(set(ss_a) & set(ss_b))}")
    out.append("")
    out.append("### Save id → same entity?")
    out.append("| reader | id → attributes | rows A → B | shared ids | same attrs | new ids in B |")
    out.append("|---|---|---|---|---|---|")
    out.append(identity(ka, kb, "players", "uid", ["unique_id", "birth_date"]))
    out.append(identity(ka, kb, "players", "uid", ["full_name", "birth_date"]))
    out.append(identity(ka, kb, "staff", "uid", ["unique_id", "birth_date"]))
    out.append(identity(ka, kb, "clubs", "uid", ["unique_id"]))
    out.append(identity(ka, kb, "clubs", "uid", ["name"]))
    out.append(identity(ka, kb, "competitions", "id", ["database_id"]))
    out.append(identity(ka, kb, "stages", "id", ["competition_id"]))
    out.append(identity(ka, kb, "nations", "nation_id", ["database_id"]))
    out.append(identity(ka, kb, "stadiums", "uid", ["name", "built_date"]))
    out.append("")
    out.append("### Game database id → same save id?")
    out.append("| reader | natural → save id | comparable | same id | notes |")
    out.append("|---|---|---|---|---|")
    out.append(reverse_identity(ka, kb, "players", "unique_id", "uid"))
    out.append(reverse_identity(ka, kb, "staff", "unique_id", "uid"))
    out.append(reverse_identity(ka, kb, "clubs", "unique_id", "uid"))
    out.append(reverse_identity(ka, kb, "competitions", "database_id", "id"))
    out.append("")
    out.append("### Event records of A still present in B")
    out.append("| reader | key (= compared values) | rows A | kept in B | same values | new in B |")
    out.append("|---|---|---|---|---|---|")
    out.append(
        overlap(
            ka,
            kb,
            "fixtures",
            ["date", "home_club_uid", "away_club_uid"],
            ["home_goals", "away_goals"],
            only=("played", True),
        )
    )
    out.append(
        overlap(
            ka,
            kb,
            "fixtures",
            ["date", "home_team_id", "away_team_id"],
            ["home_goals", "away_goals", "stage_id"],
            only=("played", True),
        )
    )
    out.append(
        overlap(
            ka,
            kb,
            "player_season_history",
            ["player_uid", "season_year", "club_uid", "kind", "competition_reference"],
            ["minutes", "goals"],
        )
    )
    out.append(
        overlap(
            ka, kb, "player_season_stats", ["player_uid", "kind", "club_uid"], ["minutes", "goals"]
        )
    )
    out.append(overlap(ka, kb, "injuries", ["player_uid", "date", "type_id"], []))
    out.append(overlap(ka, kb, "suspensions", ["player_uid", "issued_date"], []))
    out.append(overlap(ka, kb, "players", ["uid"], ["ability_current", "ability_potential"]))
    out.append(overlap(ka, kb, "players", ["uid"], ["transfer_value"]))
    out.append("")
    return "\n".join(out)


def main() -> int:
    out_dir = Path(sys.argv[1])
    stems = sys.argv[2:]
    for a, b in itertools.pairwise(stems):
        print(report(out_dir, a, b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
