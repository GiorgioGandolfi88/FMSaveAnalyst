"""SQLite connections to career databases (`*.fmsa`)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 4
CAREER_SUFFIX = ".fmsa"


def q(identifier: str) -> str:
    """Quote an SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def open_writer(path: Path) -> sqlite3.Connection:
    """Connection used only by the importer (explicit transactions)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-200000")
    return conn


def open_reader(path: Path) -> sqlite3.Connection:
    """Read-only connection (the full read-only/masking layer arrives in Step 5)."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only=ON")
    return conn
