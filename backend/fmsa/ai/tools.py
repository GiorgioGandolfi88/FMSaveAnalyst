"""Tools the AI assistants can call. All of them read the career through the masked, read-only
session, so the model never sees hidden data and can never change anything."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fmsa.api_query import describe_schema
from fmsa.query.session import QueryError, ReadOnlySession

MAX_ROWS = 200
MAX_RESULT_CHARS = 24_000

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_tables",
        "description": (
            "List the tables and views of the career database with their kind and number of "
            "columns. Call this first when you do not know where some data lives."
        ),
        "schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "describe_table",
        "description": (
            "Columns of one table or view: name, SQL type, the Football Manager field it comes "
            "from and whether it is hidden by the user's masking settings (hidden columns always "
            "read as NULL - do not try to infer them)."
        ),
        "schema": {
            "type": "object",
            "properties": {"table": {"type": "string", "description": "Table or view name"}},
            "required": ["table"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_sql",
        "description": (
            "Run one read-only SQLite SELECT (or WITH) query on the career database and get up to "
            f"{MAX_ROWS} rows. Aggregate and filter in SQL instead of fetching raw rows. The "
            "user may review every result before it is sent to you."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A single SELECT/WITH statement"},
                "purpose": {
                    "type": "string",
                    "description": "One short sentence, in the user's language, explaining why",
                },
            },
            "required": ["sql", "purpose"],
            "additionalProperties": False,
        },
    },
]


class ToolRunner:
    def __init__(self, db_path: Path, session: ReadOnlySession) -> None:
        self.db_path = db_path
        self.session = session
        self._schema: list[dict[str, Any]] | None = None

    def schema(self) -> list[dict[str, Any]]:
        if self._schema is None:
            self._schema = describe_schema(self.db_path, self.session.masked)
        return self._schema

    def run(self, name: str, args: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:
        """Returns (text sent to the model, is_error, preview for the user)."""
        try:
            if name == "list_tables":
                items = [
                    {"name": o["name"], "group": o["group"], "kind": o["kind"],
                     "columns": len(o["columns"])}
                    for o in self.schema()
                    if o["group"] != "history"
                ]  # fmt: skip
                text = json.dumps(
                    {
                        "tables": items,
                        "note": "Every view <name> has a <name>_all table with full history.",
                    }
                )
                return text, False, {"kind": "tables", "count": len(items)}
            if name == "describe_table":
                table = str(args.get("table", ""))
                obj = next((o for o in self.schema() if o["name"] == table), None)
                if obj is None:
                    return f"Unknown table {table}", True, {"kind": "error"}
                cols = [
                    {"name": c["name"], "type": c["type"], "from": c["source_path"],
                     **({"hidden": True} if c["masked"] else {})}
                    for c in obj["columns"]
                    if not c["internal"] or c["name"] in ("_rid", "_parent_rid", "_valid_from")
                ]  # fmt: skip
                text = json.dumps({"table": table, "kind": obj["kind"], "columns": cols})
                return text, False, {"kind": "columns", "table": table, "count": len(cols)}
            if name == "run_sql":
                sql = str(args.get("sql", ""))
                r = self.session.query(sql, limit=MAX_ROWS)
                payload = {
                    "columns": r.columns,
                    "rows": r.rows,
                    "row_count": len(r.rows),
                    "truncated": r.truncated,
                    "hidden_columns": r.masked,
                }
                text = json.dumps(payload, ensure_ascii=False, default=str)
                if len(text) > MAX_RESULT_CHARS:
                    keep = max(1, len(r.rows) * MAX_RESULT_CHARS // len(text))
                    payload["rows"] = r.rows[:keep]
                    payload["truncated"] = True
                    payload["note"] = f"Only the first {keep} rows are shown; aggregate in SQL."
                    text = json.dumps(payload, ensure_ascii=False, default=str)
                preview = {
                    "kind": "rows",
                    "columns": r.columns,
                    "rows": payload["rows"][:20],
                    "row_count": len(payload["rows"]),
                    "truncated": payload["truncated"],
                }
                return text, False, preview
            return f"Unknown tool {name}", True, {"kind": "error"}
        except QueryError as exc:
            return f"Query error: {exc}", True, {"kind": "error", "message": str(exc)}
