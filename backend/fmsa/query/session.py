"""The single, read-only way to query a career database.

Every query from the UI, dashboards and AI assistants goes through `ReadOnlySession`, which
layers three independent protections:

1. the file is opened with `mode=ro` (SQLite refuses any write at the file level);
2. `PRAGMA query_only = ON`;
3. an SQLite authorizer that allows only reading (SELECT, column reads, functions, recursive
   CTEs). Anything else (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, ATTACH, PRAGMA,
   transactions, …) is refused before it runs. The same authorizer answers SQLITE_IGNORE for
   masked columns, which makes SQLite read them as NULL wherever they appear in the statement.

Python's sqlite3 also refuses to run more than one statement per call.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fmsa.config import MaskingSettings
from fmsa.query.masking import ALWAYS_HIDDEN_COLUMNS, MaskRules, masked_columns

DEFAULT_ROW_LIMIT = 10_000
MAX_ROW_LIMIT = 200_000
DEFAULT_TIMEOUT_S = 30.0

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}
_QUALIFIED = re.compile(r'^(?:"?[\w]+"?\.)?"?([^".]+)"?$')
_DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


class QueryError(Exception):
    """The query was refused or failed; the message is safe to show to the user."""


@dataclass(slots=True)
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    elapsed_ms: int
    masked: list[str] = field(default_factory=list)  # result columns that are hidden

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "truncated": self.truncated,
            "elapsed_ms": self.elapsed_ms,
            "masked": self.masked,
            "row_count": len(self.rows),
        }


def _bind(params: Iterable[Any] | Mapping[str, Any]) -> Any:
    """Positional (?) or named (:name) parameters."""
    return dict(params) if isinstance(params, Mapping) else tuple(params)


def _json_value(v: Any) -> Any:
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


class ReadOnlySession:
    def __init__(
        self,
        db_path: Path,
        masked: Iterable[tuple[str, str]] = (),
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        if not db_path.is_file():
            raise QueryError(f"career database not found: {db_path}")
        self.db_path = db_path
        self.masked = {(t.lower(), c.lower()) for t, c in masked}
        self.masked_names = {c for _, c in self.masked}
        self.timeout_s = timeout_s
        self._deadline = 0.0
        self.conn = sqlite3.connect(
            f"{db_path.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False
        )
        self.conn.execute("PRAGMA query_only = ON")
        self.conn.set_authorizer(self._authorize)
        self.conn.set_progress_handler(self._progress, 20_000)

    # ------------------------------------------------------------------ guards

    def _authorize(
        self, action: int, arg1: str | None, arg2: str | None, _db: str | None, _src: str | None
    ) -> int:
        if action not in _ALLOWED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and arg1 and arg2:
            column = arg2.lower()
            if column in ALWAYS_HIDDEN_COLUMNS or (arg1.lower(), column) in self.masked:
                return sqlite3.SQLITE_IGNORE
        if action == sqlite3.SQLITE_FUNCTION and arg2 and arg2.lower() in _DENIED_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def _column_name(self, name: str) -> str:
        """SQLite names a masked (ignored) column after its expression, e.g. t1."col"."""
        m = _QUALIFIED.match(name)
        if m and m.group(1).lower() in self.masked_names:
            return m.group(1)
        return name

    def _progress(self) -> int:
        return 1 if self._deadline and time.monotonic() > self._deadline else 0

    # ------------------------------------------------------------------ API

    def query(
        self,
        sql: str,
        params: Iterable[Any] | Mapping[str, Any] = (),
        limit: int = DEFAULT_ROW_LIMIT,
    ) -> QueryResult:
        sql = sql.strip().rstrip(";").strip()
        if not sql:
            raise QueryError("empty query")
        limit = max(1, min(int(limit), MAX_ROW_LIMIT))
        start = time.monotonic()
        self._deadline = start + self.timeout_s
        try:
            cur = self.conn.execute(sql, _bind(params))
            columns = [d[0] for d in cur.description or []]
            raw = cur.fetchmany(limit + 1)
        except (sqlite3.DatabaseError, sqlite3.Warning) as exc:
            raise QueryError(self._explain(exc)) from exc
        finally:
            self._deadline = 0.0
        truncated = len(raw) > limit
        rows = [[_json_value(v) for v in r] for r in raw[:limit]]
        columns = [self._column_name(c) for c in columns]
        masked = [c for c in columns if c.lower() in self.masked_names]
        return QueryResult(
            columns=columns,
            rows=rows,
            truncated=truncated,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            masked=masked,
        )

    def stream(
        self, sql: str, params: Iterable[Any] | Mapping[str, Any] = (), timeout_s: float = 600.0
    ) -> tuple[list[str], Iterator[list[Any]]]:
        """Columns and an iterator over all rows (for exports). Same guards as query()."""
        sql = sql.strip().rstrip(";").strip()
        if not sql:
            raise QueryError("empty query")
        self._deadline = time.monotonic() + timeout_s
        try:
            cur = self.conn.execute(sql, _bind(params))
        except (sqlite3.DatabaseError, sqlite3.Warning) as exc:
            self._deadline = 0.0
            raise QueryError(self._explain(exc)) from exc
        columns = [d[0] for d in cur.description or []]

        def rows() -> Iterator[list[Any]]:
            try:
                while batch := cur.fetchmany(2000):
                    for r in batch:
                        yield [_json_value(v) for v in r]
            except sqlite3.DatabaseError as exc:
                raise QueryError(self._explain(exc)) from exc
            finally:
                self._deadline = 0.0

        return columns, rows()

    def _explain(self, exc: Exception) -> str:
        msg = str(exc)
        if "not authorized" in msg:
            return "Only read-only queries (SELECT / WITH) are allowed."
        if "interrupted" in msg:
            return f"The query was stopped after {self.timeout_s:.0f} seconds."
        if "readonly" in msg or "query_only" in msg:
            return "The career database is read-only."
        return msg

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> ReadOnlySession:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_career(
    db_path: Path, masking: MaskingSettings, timeout_s: float = DEFAULT_TIMEOUT_S
) -> ReadOnlySession:
    """A read-only session with the user's masking rules applied."""
    session = ReadOnlySession(db_path, timeout_s=timeout_s)
    hidden = masked_columns(session.conn, MaskRules.from_settings(masking))
    session.masked = hidden
    session.masked_names = {c for _, c in hidden}
    return session
