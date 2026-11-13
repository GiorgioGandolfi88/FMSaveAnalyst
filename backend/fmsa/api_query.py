"""API routes: schema of the open career and read-only SQL queries."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from fmsa.config import SettingsStore
from fmsa.db import open_reader, q
from fmsa.ingest.readers import CATEGORIES
from fmsa.query.browse import BrowseError, build_browse_sql
from fmsa.query.export import EXTENSIONS, ExportFormat, write_export
from fmsa.query.masking import ALWAYS_HIDDEN_COLUMNS
from fmsa.query.relations import derive_relations
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
                r[0]: {"reader": r[1], "kind": r[2], "parent": r[3], "base_table": r[4],
                       "record_type": r[5]}
                for r in conn.execute(
                    "SELECT table_name, reader, kind, parent_table, base_table, record_type "
                    "FROM _tables"
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
            logical = name
            for suffix in ("_all", "_history"):
                if name.endswith(suffix) and name.removesuffix(suffix) in catalog:
                    logical = name.removesuffix(suffix)
            is_history = logical != name
            info = catalog.get(logical, {})
            record_type = info.get("record_type") or ""
            if name.startswith("ref_"):
                group = "reference"
            elif is_history:
                group = "history"
            elif info:
                group = CATEGORIES.get(record_type, "other")
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


class BrowseBody(BaseModel):
    table: str
    columns: list[str] | None = None
    filter_model: dict[str, Any] = Field(default_factory=dict)
    sort_model: list[dict[str, Any]] = Field(default_factory=list)
    start: int = Field(0, ge=0)
    end: int = Field(100, ge=1)
    count: bool = True


class ExportBody(BaseModel):
    format: ExportFormat = "csv"
    sql: str | None = None
    browse: BrowseBody | None = None
    path: str | None = None  # write to this file (desktop) instead of returning it
    params: dict[str, Any] | None = None  # named parameters for `sql` (dashboard widgets)


class SavedQuery(BaseModel):
    name: str
    sql: str
    model: dict[str, Any] | None = None  # query builder state, if built visually


def saved_queries_file(data_dir: Path, career: Path) -> Path:
    digest = hashlib.sha1(str(career.resolve()).lower().encode()).hexdigest()[:8]
    return data_dir / "queries" / f"{career.stem}-{digest}.json"


def create_router(store: SettingsStore, data_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api")

    def career_path() -> Path:
        path = store.get().last_career
        if not path or not Path(path).is_file():
            raise HTTPException(409, "no career is open")
        return Path(path)

    def browse_sql(path: Path, body: BrowseBody) -> tuple[str, str, list[Any]]:
        objects = {o["name"]: o for o in describe_schema(path, set())}
        obj = objects.get(body.table)
        if obj is None:
            raise HTTPException(404, f"unknown table {body.table}")
        available = [c["name"] for c in obj["columns"]]
        try:
            return build_browse_sql(
                body.table, available, body.columns, body.filter_model, body.sort_model
            )
        except BrowseError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/schema")
    def schema() -> dict[str, Any]:
        path = career_path()
        try:
            with open_career(path, store.get().masking) as session:
                masked = session.masked
            objects = describe_schema(path, masked)
        except (QueryError, sqlite3.Error) as exc:
            raise HTTPException(400, str(exc)) from exc
        relations = [r.to_dict() for r in derive_relations(objects)]
        return {"career": str(path), "objects": objects, "relations": relations}

    @router.post("/query")
    def run_query(body: QueryBody) -> dict[str, Any]:
        path = career_path()
        try:
            with open_career(path, store.get().masking) as session:
                return session.query(body.sql, limit=body.limit).to_dict()
        except QueryError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/browse")
    def browse(body: BrowseBody) -> dict[str, Any]:
        path = career_path()
        sql, count_sql, params = browse_sql(path, body)
        size = max(1, min(body.end - body.start, 5000))
        try:
            with open_career(path, store.get().masking) as session:
                page = session.query(
                    f"{sql} LIMIT {size} OFFSET {body.start}", params, limit=size
                ).to_dict()
                total = None
                if body.count:
                    total = session.query(count_sql, params, limit=1).rows[0][0]
        except QueryError as exc:
            raise HTTPException(400, str(exc)) from exc
        page["total"] = total
        page["sql"] = sql
        page["params"] = params
        return page

    @router.post("/export", response_model=None)
    def export(body: ExportBody) -> dict[str, Any] | StreamingResponse:
        path = career_path()
        if body.browse is not None:
            sql, _, params = browse_sql(path, body.browse)
        elif body.sql:
            sql, params = body.sql, (body.params or [])
        else:
            raise HTTPException(422, "sql or browse is required")
        encoding = "utf-8-sig" if body.format == "csv_excel" else "utf-8"
        session = open_career(path, store.get().masking)
        try:
            columns, rows = session.stream(sql, params)
        except QueryError as exc:
            session.close()
            raise HTTPException(400, str(exc)) from exc
        if body.path:
            target = Path(body.path)
            try:
                with session, target.open("w", encoding=encoding, newline="") as fh:
                    n = write_export(body.format, columns, rows, fh)
            except QueryError as exc:
                target.unlink(missing_ok=True)
                raise HTTPException(400, str(exc)) from exc
            return {"path": str(target), "rows": n}

        def generate() -> Iterator[bytes]:
            with session:
                buffer = io.StringIO()
                write_export(body.format, columns, rows, buffer)
                yield buffer.getvalue().encode(encoding)

        media = "application/json" if body.format == "json" else "text/csv"
        name = f"fmsa-export{EXTENSIONS[body.format]}"
        return StreamingResponse(
            generate(),
            media_type=f"{media}; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @router.get("/saved-queries")
    def get_saved() -> list[SavedQuery]:
        file = saved_queries_file(data_dir, career_path())
        if not file.is_file():
            return []
        return [SavedQuery.model_validate(x) for x in json.loads(file.read_text("utf-8"))]

    @router.put("/saved-queries")
    def put_saved(queries: list[SavedQuery]) -> list[SavedQuery]:
        file = saved_queries_file(data_dir, career_path())
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        payload = json.dumps([x.model_dump() for x in queries], ensure_ascii=False, indent=2)
        tmp.write_text(payload, "utf-8")
        os.replace(tmp, file)
        return queries

    return router
