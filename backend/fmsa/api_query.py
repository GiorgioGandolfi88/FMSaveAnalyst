"""API routes: schema of the open career and read-only SQL queries."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fmsa.config import SettingsStore
from fmsa.db import open_reader, q
from fmsa.query.masking import ALWAYS_HIDDEN_COLUMNS
from fmsa.query.session import DEFAULT_ROW_LIMIT, MAX_ROW_LIMIT, QueryError, open_career


class QueryBody(BaseModel):
    sql: str
    limit: int = Field(DEFAULT_ROW_LIMIT, ge=1, le=MAX_ROW_LIMIT)


def describe_schema(db_path: Path, masked: set[tuple[str, str]]) -> list[dict[str, Any]]:
    """User-facing tables and views of a career database with their columns."""
    with contextlib.closing(open_reader(db_path)) as conn:
        catalog: dict[str, dict[str, Any]] = {}
        with contextlib.suppress(sqlite3.OperationalError):
            catalog = {
                r[0]: {"reader": r[1], "kind": r[2], "parent": r[3], "base_table": r[4]}
                for r in conn.execute(
                    "SELECT table_name, reader, kind, parent_table, base_table FROM _tables"
                )
            }
        sources: dict[tuple[str, str], tuple[str, str]] = {}
        with contextlib.suppress(sqlite3.OperationalError):
            sources = {
                (t, c): (p or "", s or "")
                for t, c, p, s in conn.execute(
                    "SELECT table_name, column_name, source_path, field_status FROM _columns"
                )
            }
        objects = conn.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_%' ESCAPE '\\' ORDER BY name"
        ).fetchall()
        result = []
        for name, obj_type in objects:
            is_history = name.endswith("_all") and name.removesuffix("_all") in catalog
            logical = name.removesuffix("_all") if is_history else name
            info = catalog.get(logical, {})
            if name.startswith("ref_"):
                group = "reference"
            elif is_history:
                group = "history"
            elif info:
                group = "data"
            else:
                group = "derived"
            columns = []
            for _, col, col_type, *_rest in conn.execute(f"PRAGMA table_info({q(name)})"):
                path, status = sources.get((logical, col), ("", ""))
                hidden = (
                    col.lower() in ALWAYS_HIDDEN_COLUMNS
                    or (
                        name.lower(),
                        col.lower(),
                    )
                    in masked
                )
                columns.append(
                    {
                        "name": col,
                        "type": col_type or "",
                        "masked": hidden,
                        "source_path": path,
                        "status": status,
                        "internal": col.startswith("_"),
                    }
                )
            result.append(
                {
                    "name": name,
                    "type": obj_type,
                    "group": group,
                    "kind": info.get("kind"),
                    "reader": info.get("reader"),
                    "parent": info.get("parent"),
                    "columns": columns,
                }
            )
    return result


def create_router(store: SettingsStore) -> APIRouter:
    router = APIRouter(prefix="/api")

    def career_path() -> Path:
        path = store.get().last_career
        if not path or not Path(path).is_file():
            raise HTTPException(409, "no career is open")
        return Path(path)

    @router.get("/schema")
    def schema() -> dict[str, Any]:
        path = career_path()
        try:
            with open_career(path, store.get().masking) as session:
                masked = session.masked
            return {"career": str(path), "objects": describe_schema(path, masked)}
        except (QueryError, sqlite3.Error) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/query")
    def run_query(body: QueryBody) -> dict[str, Any]:
        path = career_path()
        try:
            with open_career(path, store.get().masking) as session:
                return session.query(body.sql, limit=body.limit).to_dict()
        except QueryError as exc:
            raise HTTPException(400, str(exc)) from exc

    return router
