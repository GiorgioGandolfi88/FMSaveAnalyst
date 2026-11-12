from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from fmsa.reference import choose_version, competition_names, copy_into_career

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "build_reference", ROOT / "reference" / "build_reference.py"
)
assert _spec and _spec.loader
build_reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_reference)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def ref_db(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    write(src / "26.1.0" / "competitions.csv", "database_id,name\n1,Serie A old\n")
    write(
        src / "26.3.2" / "competitions.csv",
        "database_id,name\n1,Serie A\n2,Serie B\n3,\n",
    )
    write(src / "26.3.2" / "nations.csv", "database_id,name,short_name,code\n10,Italia,ITA,IT\n")
    write(src / "27.0.1" / "competitions.csv", "database_id,name\n1,Serie A Enilive\n")
    out = tmp_path / "ref.sqlite"
    build_reference.build(src, out)
    return out


def test_choose_version(ref_db: Path) -> None:
    exact = choose_version(ref_db, "26.3.2+2329565")
    assert exact and exact.version == "26.3.2" and exact.exact
    assert exact.tables == ("competitions", "nations")
    later = choose_version(ref_db, "26.4.0+1")
    assert later and later.version == "26.3.2" and not later.exact
    earlier = choose_version(ref_db, "26.0.5+1")
    assert earlier and earlier.version == "26.1.0"
    assert choose_version(ref_db, "28.0.0+1") is None
    assert choose_version(ref_db.with_name("missing.sqlite"), "26.3.2") is None


def test_names_and_copy(ref_db: Path, tmp_path: Path) -> None:
    choice = choose_version(ref_db, "26.3.2+1")
    assert choice
    assert competition_names(ref_db, choice) == {1: "Serie A", 2: "Serie B"}
    conn = sqlite3.connect(tmp_path / "career.fmsa")
    assert copy_into_career(conn, ref_db, choice) == 4
    assert conn.execute("SELECT name FROM ref_nations WHERE database_id = 10").fetchone() == (
        "Italia",
    )
    # a second copy replaces the first
    copy_into_career(conn, ref_db, choice)
    assert conn.execute("SELECT count(*) FROM ref_competitions").fetchone()[0] == 3


def test_build_rejects_bad_input(tmp_path: Path) -> None:
    src = tmp_path / "src"
    write(src / "26.3.2" / "competitions.csv", "id,name\n1,x\n")
    with pytest.raises(SystemExit, match="database_id"):
        build_reference.build(src, tmp_path / "r.sqlite")
    write(src / "26.3.2" / "competitions.csv", "database_id,name\n1,x\n1,y\n")
    with pytest.raises(SystemExit, match="duplicate"):
        build_reference.build(src, tmp_path / "r.sqlite")
