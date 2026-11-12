"""Import a real save. Skipped unless FMSA_TEST_SAVE (and optionally FMSA_TEST_SAVE_2,
a later save of the same career) point to Football Manager save files."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from fmsa.ingest.importer import ImportRejected, import_save

SAVE = os.environ.get("FMSA_TEST_SAVE")
SAVE_2 = os.environ.get("FMSA_TEST_SAVE_2")
READERS = ("clubs", "nations", "competitions", "stages", "fixtures", "league_tables")

pytestmark = pytest.mark.skipif(not SAVE, reason="FMSA_TEST_SAVE not set")


def test_import_real_save(tmp_path: Path) -> None:
    assert SAVE
    db = tmp_path / "career.fmsa"
    result = import_save(db, Path(SAVE), readers=READERS)
    assert {r.reader for r in result.readers} == set(READERS)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM clubs").fetchone()[0] > 1000
    assert conn.execute("SELECT count(*) FROM fixtures WHERE played = 1").fetchone()[0] > 100
    assert conn.execute("SELECT count(*) FROM league_tables__rows").fetchone()[0] > 100
    conn.close()
    with pytest.raises(ImportRejected):
        import_save(db, Path(SAVE), readers=READERS)

    if SAVE_2:
        second = import_save(db, Path(SAVE_2), readers=READERS)
        fixtures = next(r for r in second.readers if r.reader == "fixtures")
        assert fixtures.stats.unchanged > 0  # overlap with the first save
        clubs = next(r for r in second.readers if r.reader == "clubs")
        assert clubs.stats.inserted == 0
