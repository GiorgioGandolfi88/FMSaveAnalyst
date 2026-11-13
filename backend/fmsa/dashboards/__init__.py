"""Pre-built dashboards.

A dashboard is a JSON file (see defs/): a title, the filters it uses and a list of widgets, each
with its own SQL using named parameters:

- choices from the career: :club, :competition, :season, and the optional :nation and :league
  (NULL = all; on dashboards with a club they also narrow the club list in the UI);
- numbers the user can change, declared in "inputs" with a default, e.g.
  {"id": "min_ca", "default": 120, "min": 1, "max": 200, "label": {"it": "...", "en": "..."}}
  and used as :min_ca. Widget titles can show them as {min_ca};
- :today, the in-game date of the latest import. Every widget runs through the
read-only session, so masking applies to dashboards exactly as to everything else.

Extra dashboards can be dropped as JSON files into <data folder>/dashboards/; a file with the
same id as a built-in dashboard replaces it.
"""

from __future__ import annotations

import io
import json
import logging
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from fmsa.query.export import EXTENSIONS, ExportFormat, write_export
from fmsa.query.session import QueryError, ReadOnlySession

log = logging.getLogger(__name__)

BUILTIN_DIR = Path(__file__).resolve().parent / "defs"
WIDGET_ROW_LIMIT = 5000
WIDGET_TYPES = {"kpi", "table", "bar", "line", "scatter"}

PARAM_OPTIONS: dict[str, str] = {
    "club": (
        # the most famous clubs plus every club playing in a league table
        "SELECT uid AS value, name || CASE WHEN gender = 'women' THEN ' ♀' ELSE '' END "
        "AS label, nation_id FROM Club WHERE uid IN ("
        " SELECT uid FROM Club ORDER BY reputation DESC LIMIT 3000) "
        "OR uid IN (SELECT club_uid FROM LeagueTableRow) "
        "ORDER BY gender = 'women', reputation DESC"
    ),
    "competition": (
        "SELECT lt.competition_id AS value, "
        "coalesce(c.name, '#' || coalesce(c.database_id, lt.competition_id)) AS label, "
        "(SELECT r2.club_name FROM LeagueTable lt2 JOIN LeagueTableRow r2 "
        " ON r2._parent_rid = lt2._rid WHERE lt2.competition_id = lt.competition_id "
        " ORDER BY r2.position LIMIT 1) AS leader "
        "FROM LeagueTable lt LEFT JOIN Competition c ON c.id = lt.competition_id "
        "LEFT JOIN LeagueTableRow r ON r._parent_rid = lt._rid "
        "LEFT JOIN Club cl ON cl.uid = r.club_uid "
        "GROUP BY lt.competition_id ORDER BY avg(cl.reputation) DESC"
    ),
    "season": (
        "SELECT season_year AS value, season_year AS label, count(*) AS n "
        "FROM PlayerSeasonHistory WHERE kind = 'league' "
        "GROUP BY season_year ORDER BY season_year DESC"
    ),
    "nation": (
        # saves do not store nation names: show the reference name when there is one, else
        # the nation's three most famous clubs
        "SELECT nation_id AS value, group_concat(name, ', ') AS clubs, max(rep) AS rep "
        "FROM (SELECT nation_id, name, rep, row_number() OVER "
        " (PARTITION BY nation_id ORDER BY rep DESC) AS rn FROM ("
        "  SELECT nation_id, name, max(reputation) AS rep FROM Club "
        "  WHERE nation_id IS NOT NULL AND reputation IS NOT NULL GROUP BY nation_id, name)) "
        "WHERE rn <= 3 GROUP BY nation_id ORDER BY rep DESC"
    ),
}
# used when the career has no league tables
CLUB_FALLBACK = (
    "SELECT uid AS value, name || CASE WHEN gender = 'women' THEN ' ♀' ELSE '' END "
    "AS label, nation_id FROM Club ORDER BY gender = 'women', reputation DESC LIMIT 3000"
)
OPTIONAL_PARAMS = frozenset({"nation", "league"})  # NULL = no filter
# "league" offers the competition options
CHOICE_PARAMS = frozenset(PARAM_OPTIONS) | OPTIONAL_PARAMS


class DashboardError(ValueError):
    pass


def _validate(d: dict[str, Any], source: Path) -> dict[str, Any]:
    if not isinstance(d.get("id"), str) or not isinstance(d.get("widgets"), list):
        raise DashboardError(f"{source.name}: 'id' and 'widgets' are required")
    for p in d.get("params", []):
        if p not in CHOICE_PARAMS:
            raise DashboardError(f"{source.name}: unknown parameter {p}")
    for i in d.setdefault("inputs", []):
        if not isinstance(i, dict) or not str(i.get("id", "")).isidentifier():
            raise DashboardError(f"{source.name}: an input needs an id")
        if i["id"] in CHOICE_PARAMS or i["id"] == "today":
            raise DashboardError(f"{source.name}: input {i['id']} clashes with a parameter")
        if not isinstance(i.get("default"), (int, float)):
            raise DashboardError(f"{source.name}: input {i['id']} needs a numeric default")
    for w in d["widgets"]:
        if w.get("type") not in WIDGET_TYPES or not w.get("sql") or not w.get("id"):
            raise DashboardError(f"{source.name}: widget needs id, sql and a known type")
    d.setdefault("params", [])
    d.setdefault("order", 100)
    d["source"] = "builtin" if source.parent == BUILTIN_DIR else "user"
    return d


def load_dashboards(user_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    folders = [BUILTIN_DIR] + ([user_dir] if user_dir and user_dir.is_dir() else [])
    for folder in folders:
        for file in sorted(folder.glob("*.json")):
            try:
                d = _validate(json.loads(file.read_text(encoding="utf-8")), file)
            except (OSError, ValueError) as exc:
                log.warning("Dashboard %s ignored: %s", file, exc)
                continue
            found[d["id"]] = d
    return dict(sorted(found.items(), key=lambda kv: (kv[1]["order"], kv[0])))


def _nation_names(session: ReadOnlySession) -> dict[Any, str]:
    try:
        rows = session.query(
            "SELECT nation_id, name FROM nation_names WHERE name IS NOT NULL", limit=5000
        ).rows
    except QueryError:
        return {}
    return {r[0]: str(r[1]) for r in rows}


def _club_leagues(session: ReadOnlySession) -> dict[Any, list[Any]]:
    try:
        rows = session.query(
            "SELECT DISTINCT r.club_uid, lt.competition_id FROM LeagueTable lt "
            "JOIN LeagueTableRow r ON r._parent_rid = lt._rid "
            "WHERE r.club_uid IS NOT NULL AND lt.competition_id IS NOT NULL",
            limit=100_000,
        ).rows
    except QueryError:
        return {}
    out: dict[Any, list[Any]] = {}
    for club, competition in rows:
        out.setdefault(club, []).append(competition)
    return out


def param_options(session: ReadOnlySession) -> dict[str, Any]:
    """Options and defaults for every dashboard parameter, plus today's in-game date.

    Club options also carry `nation` and `leagues`, so the UI can narrow the club list."""
    out: dict[str, Any] = {}
    names = _nation_names(session)
    leagues = _club_leagues(session)
    for name, sql in PARAM_OPTIONS.items():
        try:
            r = session.query(sql, limit=50_000)
        except QueryError:
            try:
                if name != "club":
                    raise
                r = session.query(CLUB_FALLBACK, limit=50_000)
            except QueryError:
                out[name] = {"options": [], "default": None}
                continue
        options = []
        for row in r.rows:
            value, label = row[0], str(row[1])
            option: dict[str, Any] = {"value": value, "label": label}
            if name == "competition" and len(row) > 2 and row[2]:
                option["label"] = f"{label} · {row[2]}"
            elif name == "club":
                option["nation"] = row[2]
                option["leagues"] = leagues.get(value, [])
            elif name == "nation":
                option["label"] = names.get(value) or f"#{value} · {label}"
            options.append(option)
        default = options[0]["value"] if options else None
        if name == "season" and r.rows:
            # the newest season may have just started: default to the latest one with data
            biggest = max(row[2] for row in r.rows)
            default = next(row[0] for row in r.rows if row[2] >= biggest * 0.25)
        if name == "nation":
            default = None
        out[name] = {"options": options, "default": default}
    out["league"] = {"options": out["competition"]["options"], "default": None}
    try:
        managed = session.query("SELECT club_uid FROM ManagedClub LIMIT 1").rows
        if managed:
            out["club"]["default"] = managed[0][0]
    except QueryError:
        pass
    try:
        today = session.query(
            "SELECT max(game_date) FROM _imports WHERE status = 'ok'", limit=1
        ).rows[0][0]
    except (QueryError, IndexError):
        today = None
    out["today"] = today
    return out


def _bind(d: dict[str, Any], params: dict[str, Any], today: str | None) -> dict[str, Any]:
    values: dict[str, Any] = {name: params.get(name) for name in CHOICE_PARAMS}
    for i in d.get("inputs", []):
        v = params.get(i["id"])
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            v = i["default"]
        if "min" in i:
            v = max(v, i["min"])
        if "max" in i:
            v = min(v, i["max"])
        values[i["id"]] = v
    values["today"] = today
    return values


def run_dashboard(
    session: ReadOnlySession, d: dict[str, Any], params: dict[str, Any], today: str | None
) -> dict[str, Any]:
    values = _bind(d, params, today)
    results: dict[str, Any] = {}
    for w in d["widgets"]:
        try:
            results[w["id"]] = session.query(w["sql"], values, limit=WIDGET_ROW_LIMIT).to_dict()
        except (QueryError, sqlite3.Error) as exc:
            results[w["id"]] = {"error": str(exc)}
    return results


def export_dashboard(
    session: ReadOnlySession,
    d: dict[str, Any],
    params: dict[str, Any],
    today: str | None,
    fmt: ExportFormat,
) -> bytes:
    """A zip with one file per widget plus the parameters used."""
    values = _bind(d, params, today)
    buffer = io.BytesIO()
    encoding = "utf-8-sig" if fmt == "csv_excel" else "utf-8"
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "parameters.json",
            json.dumps({"dashboard": d["id"], **values}, ensure_ascii=False, indent=2),
        )
        for i, w in enumerate(d["widgets"], start=1):
            try:
                columns, rows = session.stream(w["sql"], values)
            except QueryError as exc:
                z.writestr(f"{i:02d}_{w['id']}.error.txt", str(exc))
                continue
            text = io.StringIO()
            write_export(fmt, columns, rows, text)
            z.writestr(f"{i:02d}_{w['id']}{EXTENSIONS[fmt]}", text.getvalue().encode(encoding))
    return buffer.getvalue()
