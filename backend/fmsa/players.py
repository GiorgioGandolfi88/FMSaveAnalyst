"""Player list and player card.

Everything is read through the read-only session, so the user's masking applies: a hidden
column (potential, hidden attributes, personality, ...) reads as NULL and is never ranked.

Ranks are percentiles against the players of the same role in this save. A player's role group
comes from his first natural position (`natural_positions`); the group holds every player with a
natural position of that group ("ranked as wingers").
"""

from __future__ import annotations

import bisect
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fmsa.query.session import QueryError, ReadOnlySession

# role groups: key -> (positions, short label for the wheel)
GROUPS: dict[str, tuple[tuple[str, ...], str]] = {
    "goalkeepers": (("GK",), "GK"),
    "centre_backs": (("DC", "SW"), "CB"),
    "full_backs": (("DL", "DR", "WBL", "WBR"), "FB"),
    "defensive_midfielders": (("DM",), "DM"),
    "central_midfielders": (("MC",), "CM"),
    "wingers": (("ML", "MR", "AML", "AMR"), "W"),
    "attacking_midfielders": (("AMC",), "AM"),
    "strikers": (("STC",), "ST"),
}
POSITIONS = ("gk", "sw", "dl", "dc", "dr", "wbl", "wbr", "dm", "ml", "mc", "mr", "aml", "amc",
             "amr", "stc")  # fmt: skip

ATTRIBUTES: dict[str, tuple[str, ...]] = {
    "technical": ("corners", "crossing", "dribbling", "finishing", "first_touch",
                  "free_kick_taking", "heading", "long_shots", "long_throws", "marking",
                  "passing", "penalty_taking", "tackling", "technique"),
    "mental": ("aggression", "anticipation", "bravery", "composure", "concentration",
               "decisions", "determination", "flair", "leadership", "off_the_ball",
               "positioning", "teamwork", "vision", "work_rate"),
    "physical": ("acceleration", "agility", "balance", "jumping_reach", "natural_fitness",
                 "pace", "stamina", "strength"),
    "goalkeeping": ("aerial_reach", "command_of_area", "communication", "eccentricity",
                    "handling", "kicking", "one_on_ones", "punching", "reflexes", "rushing_out",
                    "throwing"),
    "hidden": ("consistency", "dirtiness", "important_matches", "injury_proneness",
               "versatility"),
}  # fmt: skip
LOWER_IS_BETTER_ATTRIBUTES = frozenset({"dirtiness", "injury_proneness"})
PERSONALITY = ("adaptability", "ambition", "loyalty", "pressure", "professionalism",
               "sportsmanship", "temperament", "controversy")  # fmt: skip

STAT_KINDS = ("league", "overall", "cup", "continental", "international", "non_competitive",
              "calendar_year_overall", "calendar_year_international")  # fmt: skip
MIN_MINUTES = 450  # players ranked in a stat need at least this many minutes


@dataclass(frozen=True, slots=True)
class Stat:
    section: str
    key: str
    kind: str  # "count": total + per 90 | "plain": total only | "rate": ratio | "rating"
    num: tuple[str, ...] = ()  # rate numerator columns (summed)
    den: tuple[str, ...] = ()  # rate denominator columns (summed)
    lower_is_better: bool = False


def _c(section: str, key: str, lower: bool = False) -> Stat:
    return Stat(section, key, "count", lower_is_better=lower)


def _r(section: str, key: str, num: tuple[str, ...], den: tuple[str, ...]) -> Stat:
    return Stat(section, key, "rate", num, den)


STATS: tuple[Stat, ...] = (
    Stat("general", "appearances", "plain"),
    Stat("general", "starts", "plain"),
    Stat("general", "substitute_appearances", "plain"),
    Stat("general", "minutes", "plain"),
    Stat("general", "average_rating", "rating"),
    _c("general", "player_of_the_match"),
    _c("general", "distance_km"),
    _c("general", "high_intensity_sprints"),
    _c("shooting", "goals"),
    _c("shooting", "expected_goals"),
    _c("shooting", "non_penalty_expected_goals"),
    _c("shooting", "shots"),
    _c("shooting", "shots_on_target"),
    _r("shooting", "shots_on_target_ratio", ("shots_on_target",), ("shots",)),
    _r("shooting", "conversion_rate", ("goals",), ("shots",)),
    _r("shooting", "expected_goals_per_shot", ("expected_goals",), ("shots",)),
    _c("shooting", "shots_outside_box"),
    _c("shooting", "goals_outside_box"),
    _c("shooting", "free_kick_shots"),
    _c("shooting", "penalties_taken"),
    _c("shooting", "penalties_scored"),
    _c("creation", "assists"),
    _c("creation", "expected_assists"),
    _c("creation", "key_passes"),
    _c("creation", "open_play_key_passes"),
    _c("creation", "clear_cut_chances_created"),
    _c("creation", "crosses_attempted"),
    _c("creation", "crosses_completed"),
    _r("creation", "cross_completion", ("crosses_completed",), ("crosses_attempted",)),
    _c("passing", "passes_attempted"),
    _c("passing", "passes_completed"),
    _r("passing", "pass_completion", ("passes_completed",), ("passes_attempted",)),
    _c("passing", "progressive_passes"),
    _c("passing", "dribbles"),
    _c("passing", "offsides", lower=True),
    _c("defending", "tackles_attempted"),
    _c("defending", "tackles_completed"),
    _r("defending", "tackle_completion", ("tackles_completed",), ("tackles_attempted",)),
    _c("defending", "key_tackles"),
    _c("defending", "interceptions"),
    _c("defending", "possession_won"),
    _c("defending", "pressures_attempted"),
    _c("defending", "pressures_completed"),
    _c("defending", "blocks"),
    _c("defending", "shots_blocked"),
    _c("defending", "clearances"),
    _c("aerial", "aerial_challenges_attempted"),
    _c("aerial", "headers_won"),
    _r("aerial", "headers_won_ratio", ("headers_won",), ("aerial_challenges_attempted",)),
    _c("aerial", "key_headers"),
    _c("discipline", "fouls_made", lower=True),
    _c("discipline", "fouls_against"),
    _c("discipline", "yellow_cards", lower=True),
    _c("discipline", "red_cards", lower=True),
    _c("discipline", "mistakes_leading_to_goal", lower=True),
    _c("discipline", "possession_lost", lower=True),
    _c("goalkeeping", "clean_sheets"),
    _c("goalkeeping", "goals_allowed", lower=True),
    _c("goalkeeping", "saves_held"),
    _c("goalkeeping", "saves_parried"),
    _c("goalkeeping", "saves_tipped"),
    _c("goalkeeping", "shots_on_target_faced"),
    _r("goalkeeping", "save_ratio", ("saves_held", "saves_parried", "saves_tipped"),
       ("shots_on_target_faced",)),
    _c("goalkeeping", "expected_goals_prevented"),
)  # fmt: skip
# raw columns summed per player
SUM_COLUMNS: tuple[str, ...] = tuple(
    dict.fromkeys(
        ["starts", "substitute_appearances", "minutes", "rated_appearances"]
        + [s.key for s in STATS if s.kind in ("count", "plain") and s.key != "appearances"]
        + [c for s in STATS for c in (*s.num, *s.den)]
    )
)

# list columns: key -> SQL expression (sortable)
LIST_COLUMNS: dict[str, str] = {
    "name": "p.name",
    "age": "p.age",
    "ca": "p.ability_current",
    "pa": "p.ability_potential",
    "club": "p.club_name",
    "value": "p.transfer_value",
    "wage": "p.contract_wage",
    "expires": "p.contract_end",
    "apps": "st.apps",
    "goals": "st.goals",
    "assists": "st.assists",
    "rating": "st.rating",
}
STATS_CTE = (
    "st AS (SELECT player_uid, sum(starts) + sum(substitute_appearances) AS apps, "
    "sum(goals) AS goals, sum(assists) AS assists, "
    "sum(average_rating * rated_appearances) / nullif(sum(rated_appearances), 0) AS rating "
    "FROM player_season_stats WHERE kind = :kind GROUP BY player_uid)"
)


class PlayerError(ValueError):
    pass


def group_of(natural_positions: list[str]) -> str | None:
    for pos in natural_positions:
        for key, (positions, _) in GROUPS.items():
            if pos in positions:
                return key
    return None


def _group_sql(group: str, alias: str = "p") -> str:
    positions = ", ".join(f"'{x}'" for x in GROUPS[group][0])
    return (
        f"EXISTS (SELECT 1 FROM json_each({alias}.natural_positions) "
        f"WHERE json_each.value IN ({positions}))"
    )


def _json_list(text: Any) -> list[Any]:
    try:
        v = json.loads(text) if isinstance(text, str) else text
    except ValueError:
        return []
    return list(v) if isinstance(v, list) else []


def _hidden(session: ReadOnlySession, table: str, column: str) -> bool:
    return (table.lower(), column.lower()) in session.masked


def _percentile(sorted_values: list[float], value: float, lower_is_better: bool = False) -> int:
    """Share of the group below `value` (ties count half), 0-100."""
    n = len(sorted_values)
    if not n:
        return 0
    lo = bisect.bisect_left(sorted_values, value)
    hi = bisect.bisect_right(sorted_values, value)
    below = (n - hi) if lower_is_better else lo
    return round(100 * (below + (hi - lo) / 2) / n)


# ---------------------------------------------------------------------------- list


def list_players(
    session: ReadOnlySession,
    *,
    search: str = "",
    group: str = "",
    only: list[tuple[int, str]] | None = None,
    kind: str = "league",
    sort: str = "pa",
    desc: bool = True,
    offset: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    if kind not in STAT_KINDS:
        raise PlayerError(f"unknown statistics kind {kind}")
    if sort not in LIST_COLUMNS:
        raise PlayerError(f"cannot sort by {sort}")
    where: list[str] = []
    params: dict[str, Any] = {"kind": kind}
    if search.strip():
        where.append("p.name LIKE :search ESCAPE '\\'")
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["search"] = f"%{escaped}%"
    if group:
        if group not in GROUPS:
            raise PlayerError(f"unknown role group {group}")
        where.append(_group_sql(group))
    if only is not None:
        if not only:
            return {"total": 0, "rows": [], "masked": [], "cutoffs": {}}
        pairs = []
        for i, (uid, born) in enumerate(only[:2000]):
            params[f"u{i}"], params[f"b{i}"] = int(uid), str(born)
            pairs.append(f"(:u{i}, :b{i})")
        where.append(f"(p.uid, p.birth_date) IN (VALUES {', '.join(pairs)})")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    order = f"{LIST_COLUMNS[sort]} {'DESC' if desc else 'ASC'} NULLS LAST, p.name"
    sql = (
        f"WITH {STATS_CTE} SELECT p.uid, p.birth_date, p.name, p.age, p.natural_positions, "
        "p.ability_current AS ca, p.ability_potential AS pa, p.club_name, p.transfer_value, "
        "p.contract_wage, p.contract_end, st.apps, st.goals, st.assists, st.rating "
        f"FROM players p LEFT JOIN st ON st.player_uid = p.uid {clause} ORDER BY {order} "
        f"LIMIT {max(1, min(limit, 500))} OFFSET {max(0, offset)}"
    )
    try:
        page = session.query(sql, params, limit=500)
        total = session.query(f"SELECT count(*) FROM players p {clause}", params, limit=1)
    except QueryError as exc:
        raise PlayerError(str(exc)) from exc
    rows = []
    for r in page.rows:
        rec = dict(zip(page.columns, r, strict=True))
        rec["natural_positions"] = _json_list(rec["natural_positions"])
        rows.append(rec)
    masked = [c for c in ("ca", "pa") if _hidden(session, "players", {
        "ca": "ability_current", "pa": "ability_potential"}[c])]  # fmt: skip
    return {
        "total": total.rows[0][0],
        "rows": rows,
        "masked": masked,
        "cutoffs": list_cutoffs(session, kind),
    }


_CUTOFFS: dict[tuple[str, str], dict[str, list[float]]] = {}
_CUTOFFS_LOCK = threading.Lock()


def list_cutoffs(session: ReadOnlySession, kind: str) -> dict[str, list[float]]:
    """Values at the 60th and 85th percentile of players who played (shading in the list)."""
    key = (str(session.db_path), kind)
    with _CUTOFFS_LOCK:
        if key in _CUTOFFS:
            return _CUTOFFS[key]
    r = session.query(
        f"WITH {STATS_CTE} SELECT apps, goals, assists, rating FROM st WHERE apps > 0",
        {"kind": kind},
        limit=200_000,
    )
    out: dict[str, list[float]] = {}
    for i, name in enumerate(r.columns):
        values = sorted(v[i] for v in r.rows if v[i] is not None)
        if values:
            out[name] = [values[int(len(values) * 0.6)], values[int(len(values) * 0.85)]]
    with _CUTOFFS_LOCK:
        _CUTOFFS[key] = out
    return out


# ---------------------------------------------------------------------------- card


def _player_row(session: ReadOnlySession, uid: int, birth_date: str) -> dict[str, Any]:
    r = session.query(
        "SELECT * FROM players WHERE uid = :uid AND birth_date = :born LIMIT 1",
        {"uid": uid, "born": birth_date},
        limit=1,
    )
    if not r.rows:
        raise PlayerError("player not found")
    return dict(zip(r.columns, r.rows[0], strict=True))


def _attribute_ranks(
    session: ReadOnlySession, p: dict[str, Any], group: str | None
) -> dict[str, int]:
    names = [a for attrs in ATTRIBUTES.values() for a in attrs]
    names = [a for a in names if p.get(f"attributes_{a}") is not None]
    if not group or not names:
        return {}
    parts = []
    params: dict[str, Any] = {}
    for i, a in enumerate(names):
        col = f"attributes_{a}"
        params[f"v{i}"] = p[col]
        op = ">" if a in LOWER_IS_BETTER_ATTRIBUTES else "<"
        parts.append(f"sum({col} {op} :v{i}) + 0.5 * sum({col} = :v{i})")
    parts.append("count(*)")
    r = session.query(
        f"SELECT {', '.join(parts)} FROM players p WHERE {_group_sql(group)}", params, limit=1
    )
    row = r.rows[0]
    n = row[-1] or 0
    return {a: round(100 * (row[i] or 0) / n) if n else 0 for i, a in enumerate(names)}


def _wheel(group: str | None, ranks: dict[str, int]) -> dict[str, Any]:
    """Centre of the attribute wheel: average rank of the attributes that matter for the role
    (goalkeeping instead of technical for goalkeepers), hidden attributes left out."""
    sections = ("goalkeeping" if group == "goalkeepers" else "technical", "mental", "physical")
    values = [ranks[a] for sec in sections for a in ATTRIBUTES[sec] if a in ranks]
    return {
        "percentile": round(sum(values) / len(values)) if values else None,
        "group": group,
        "label": GROUPS[group][1] if group else None,
    }


def _stat_values(totals: dict[str, float], stat: Stat) -> tuple[float | None, float | None]:
    """(total, per 90) of one stat from a player's summed columns."""
    minutes = totals.get("minutes") or 0
    if stat.key == "appearances":
        return (totals.get("starts") or 0) + (totals.get("substitute_appearances") or 0), None
    if stat.kind == "plain":
        return totals.get(stat.key), None
    if stat.kind == "rating":
        rated = totals.get("rated_appearances") or 0
        return (totals.get("rating_sum", 0) / rated if rated else None), None
    if stat.kind == "rate":
        den = sum(totals.get(c) or 0 for c in stat.den)
        return (sum(totals.get(c) or 0 for c in stat.num) / den if den else None), None
    total = totals.get(stat.key)
    per90 = total * 90 / minutes if total is not None and minutes else None
    return total, per90


def _stat_columns(session: ReadOnlySession) -> list[str]:
    """SUM_COLUMNS that the career's player_season_stats table actually has."""
    present = set(session.query("SELECT * FROM player_season_stats LIMIT 0").columns)
    return [c for c in SUM_COLUMNS if c in present]


def _stats(session: ReadOnlySession, uid: int, group: str | None, kind: str) -> dict[str, Any]:
    sums = ", ".join(f"sum({c}) AS {c}" for c in _stat_columns(session))
    rating = "sum(average_rating * rated_appearances) AS rating_sum"
    mine = session.query(
        f"SELECT {sums}, {rating} FROM player_season_stats "
        "WHERE player_uid = :uid AND kind = :kind",
        {"uid": uid, "kind": kind},
        limit=1,
    )
    totals = dict(zip(mine.columns, mine.rows[0], strict=True)) if mine.rows else {}
    if not totals.get("minutes") and not totals.get("starts"):
        return {"kind": kind, "rows": [], "group_size": 0}
    peers: list[dict[str, Any]] = []
    if group:
        r = session.query(
            f"SELECT {sums}, {rating} FROM player_season_stats s JOIN players p "
            f"ON p.uid = s.player_uid WHERE s.kind = :kind AND {_group_sql(group)} "
            f"GROUP BY s.player_uid HAVING sum(s.minutes) >= {MIN_MINUTES}",
            {"kind": kind},
            limit=200_000,
        )
        peers = [dict(zip(r.columns, row, strict=True)) for row in r.rows]
    rows = []
    for stat in STATS:
        total, per90 = _stat_values(totals, stat)
        if total is None:
            continue
        mine_value = per90 if per90 is not None else total
        values = sorted(
            v for v in (
                (lambda t, p9: p9 if stat.kind == "count" else t)(*_stat_values(peer, stat))
                for peer in peers
            ) if v is not None
        )  # fmt: skip
        rank = (
            _percentile(values, mine_value, stat.lower_is_better)
            if values and mine_value is not None and (totals.get("minutes") or 0) >= MIN_MINUTES
            else None
        )
        rows.append({"section": stat.section, "key": stat.key, "kind": stat.kind,
                     "total": total, "per90": per90, "rank": rank})  # fmt: skip
    return {"kind": kind, "rows": rows, "group_size": len(peers)}


def stat_kinds(session: ReadOnlySession, uid: int) -> list[str]:
    r = session.query(
        "SELECT DISTINCT kind FROM player_season_stats WHERE player_uid = :uid", {"uid": uid}
    )
    present = {row[0] for row in r.rows}
    return [k for k in STAT_KINDS if k in present]


def _contract(session: ReadOnlySession, uid: int) -> dict[str, Any] | None:
    r = session.query("SELECT * FROM contracts WHERE player_uid = :uid LIMIT 1", {"uid": uid})
    if not r.rows:
        return None
    c = dict(zip(r.columns, r.rows[0], strict=True))
    clauses = session.query(
        "SELECT kind, parameter, value FROM contracts_clauses WHERE _import_id = :i "
        "AND contracts_idx = :x ORDER BY clauses_idx",
        {"i": c["_import_id"], "x": c["contracts_idx"]},
    )
    return {
        "club_name": c.get("club_name"),
        "squad_status": c.get("squad_status"),
        "kind": c.get("kind"),
        "wage": c.get("wage"),
        "start": c.get("start"),
        "end": c.get("end"),
        "on_loan": c.get("on_loan"),
        "loan_parent_club_name": c.get("loan_parent_club_name"),
        "loan_end": c.get("loan_end"),
        "clauses": [dict(zip(clauses.columns, row, strict=True)) for row in clauses.rows],
    }


def player_card(session: ReadOnlySession, uid: int, birth_date: str, kind: str = "") -> dict:
    p = _player_row(session, uid, birth_date)
    natural = _json_list(p.get("natural_positions"))
    group = group_of(natural)
    ranks = _attribute_ranks(session, p, group)
    attributes = {
        section: [
            {"key": a, "value": p.get(f"attributes_{a}"), "rank": ranks.get(a),
             "hidden": _hidden(session, "players", f"attributes_{a}")}
            for a in attrs
        ]
        for section, attrs in ATTRIBUTES.items()
    }  # fmt: skip
    kinds = stat_kinds(session, uid)
    chosen = kind if kind in kinds else ("league" if "league" in kinds else (kinds or [""])[0])
    traits = [t for t in _json_list(p.get("traits")) if t and t != "unknown"]
    return {
        "uid": uid,
        "birth_date": birth_date,
        "name": p.get("name"),
        "age": p.get("age"),
        "nation_id": p.get("nation_id"),
        "height_cm": p.get("height_cm"),
        "club_name": p.get("club_name"),
        "club_uid": p.get("club_uid"),
        "natural_positions": natural,
        "accomplished_positions": _json_list(p.get("accomplished_positions")),
        "group": group,
        "ability_current": p.get("ability_current"),
        "ability_potential": p.get("ability_potential"),
        "ca_hidden": _hidden(session, "players", "ability_current"),
        "pa_hidden": _hidden(session, "players", "ability_potential"),
        "transfer_value": p.get("transfer_value"),
        "wage": p.get("contract_wage"),
        "contract_end": p.get("contract_end"),
        "left_foot": p.get("left_foot"),
        "right_foot": p.get("right_foot"),
        "condition": p.get("raw_condition"),
        "match_sharpness": p.get("raw_match_sharpness"),
        "club_join_date": p.get("club_join_date"),
        "on_loan": p.get("on_loan"),
        "loan_parent_club_name": p.get("loan_parent_club_name"),
        "reputation": {k: p.get(f"reputation_{k}") for k in ("current", "home", "world")},
        "personality": [
            {
                "key": k,
                "value": p.get(f"personality_{k}"),
                "hidden": _hidden(session, "players", f"personality_{k}"),
            }
            for k in PERSONALITY
        ],
        "traits": traits,
        "positions": {pos: p.get(f"positions_{pos}") for pos in POSITIONS},
        "attributes": attributes,
        "wheel": _wheel(group, ranks),
        "stat_kinds": kinds,
        "stats": _stats(session, uid, group, chosen) if chosen else None,
        "season": _season_summary(session, uid),
        "contract": _contract(session, uid),
    }


def _season_summary(session: ReadOnlySession, uid: int) -> dict[str, Any]:
    r = session.query(
        "SELECT sum(starts) + sum(substitute_appearances), sum(goals), "
        "sum(average_rating * rated_appearances) / nullif(sum(rated_appearances), 0) "
        "FROM player_season_stats WHERE player_uid = :uid AND kind = 'league'",
        {"uid": uid},
        limit=1,
    )
    apps, goals, rating = r.rows[0] if r.rows else (None, None, None)
    return {"apps": apps, "goals": goals, "rating": rating}


def player_stats(session: ReadOnlySession, uid: int, birth_date: str, kind: str) -> dict:
    p = _player_row(session, uid, birth_date)
    group = group_of(_json_list(p.get("natural_positions")))
    if kind not in STAT_KINDS:
        raise PlayerError(f"unknown statistics kind {kind}")
    return _stats(session, uid, group, kind)


# ---------------------------------------------------------------------------- shortlist


def shortlist_file(data_dir: Path, career: Path) -> Path:
    from fmsa.careers import career_side_file

    return career_side_file(data_dir, career, "shortlists")


def read_shortlist(data_dir: Path, career: Path) -> list[dict[str, Any]]:
    try:
        items = json.loads(shortlist_file(data_dir, career).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [i for i in items if isinstance(i, dict) and "uid" in i and "birth_date" in i]


def write_shortlist(data_dir: Path, career: Path, items: list[dict[str, Any]]) -> None:
    file = shortlist_file(data_dir, career)
    file.parent.mkdir(parents=True, exist_ok=True)
    clean = [{"uid": int(i["uid"]), "birth_date": str(i["birth_date"])} for i in items]
    file.write_text(json.dumps(clean), encoding="utf-8")
