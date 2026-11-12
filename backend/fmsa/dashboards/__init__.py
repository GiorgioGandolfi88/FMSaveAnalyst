"""Pre-built dashboards.

A dashboard is a JSON file (see defs/): a title, the filters it uses (club, competition, season)
and a list of widgets, each with its own SQL using named parameters (:club, :competition,
:season and :today, the in-game date of the latest import). Every widget runs through the
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
        "SELECT uid AS value, name || CASE WHEN gender_label = 'WOMEN' THEN ' ♀' ELSE '' END "
        "AS label FROM clubs ORDER BY gender_label = 'WOMEN', reputation DESC LIMIT 3000"
    ),
    "competition": (
        "SELECT lt.competition_id AS value, "
        "coalesce(c.name, '#' || coalesce(c.database_id, lt.competition_id)) AS label, "
        "(SELECT r2.club_name FROM league_tables lt2 JOIN league_tables__rows r2 "
        " ON r2._parent_rid = lt2._rid WHERE lt2.competition_id = lt.competition_id "
        " ORDER BY r2.position LIMIT 1) AS leader "
        "FROM league_tables lt LEFT JOIN competitions c ON c.id = lt.competition_id "
        "LEFT JOIN league_tables__rows r ON r._parent_rid = lt._rid "
        "LEFT JOIN clubs cl ON cl.uid = r.club_uid "
        "GROUP BY lt.competition_id ORDER BY avg(cl.reputation) DESC"
    ),
    "season": (
        "SELECT season_year AS value, season_year AS label, count(*) AS n "
        "FROM player_season_history WHERE kind = 'league' "
        "GROUP BY season_year ORDER BY season_year DESC"
    ),
}


class DashboardError(ValueError):
    pass


def _validate(d: dict[str, Any], source: Path) -> dict[str, Any]:
    if not isinstance(d.get("id"), str) or not isinstance(d.get("widgets"), list):
        raise DashboardError(f"{source.name}: 'id' and 'widgets' are required")
    for p in d.get("params", []):
        if p not in PARAM_OPTIONS:
            raise DashboardError(f"{source.name}: unknown parameter {p}")
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


def param_options(session: ReadOnlySession) -> dict[str, Any]:
    """Options and defaults for every dashboard parameter, plus today's in-game date."""
    out: dict[str, Any] = {}
    for name, sql in PARAM_OPTIONS.items():
        try:
            r = session.query(sql, limit=5000)
        except QueryError:
            out[name] = {"options": [], "default": None}
            continue
        options = []
        for row in r.rows:
            value, label = row[0], str(row[1])
            if name == "competition" and len(row) > 2 and row[2]:
                label = f"{label} · {row[2]}"
            options.append({"value": value, "label": label})
        default = options[0]["value"] if options else None
        if name == "season" and r.rows:
            # the newest season may have just started: default to the latest one with data
            biggest = max(row[2] for row in r.rows)
            default = next(row[0] for row in r.rows if row[2] >= biggest * 0.25)
        out[name] = {"options": options, "default": default}
    try:
        managed = session.query("SELECT club_uid FROM managed_clubs LIMIT 1").rows
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
    values = {name: params.get(name) for name in PARAM_OPTIONS}
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
