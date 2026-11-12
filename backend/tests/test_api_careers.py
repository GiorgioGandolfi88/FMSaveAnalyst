from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fmsa.careers import career_file_name
from fmsa.config import SettingsStore
from fmsa.ingest.importer import META_DDL
from fmsa.paths import PORTABLE_FLAG, AppPaths
from fmsa.server import TOKEN_HEADER, create_app

H = {TOKEN_HEADER: "t"}


@pytest.fixture
def setup(tmp_path: Path) -> tuple[TestClient, SettingsStore, Path]:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / PORTABLE_FLAG).touch()
    paths = AppPaths.resolve(app_dir=app_dir, bundle_dir=tmp_path / "bundle")
    paths.ensure()
    store = SettingsStore(paths)
    saves = tmp_path / "games"
    saves.mkdir()
    (saves / "Mario - Juventus.fm").write_bytes(b"x" * 10)
    (saves / "notes.txt").write_text("no")
    store.save(store.get().model_copy(update={"fm_save_dir": str(saves)}))
    client = TestClient(create_app(paths, store, "t"), base_url="http://127.0.0.1")
    return client, store, saves


def make_career(path: Path, name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(META_DDL)
    conn.executemany("INSERT INTO _meta VALUES (?, ?)", [("game", "FM26"), ("career_name", name)])
    conn.execute(
        "INSERT INTO _imports (file_name, game_date, status, manager_name) "
        "VALUES ('s1.fm', '2026-06-15', 'ok', 'Mario')"
    )
    conn.execute(
        "INSERT INTO _import_readers VALUES (1, 'officials', 'unsupported', 0, 0, 0, 0, 0, 0, 'x')"
    )
    conn.commit()
    conn.close()


def test_career_file_name() -> None:
    assert career_file_name("Mario: Juve/Real?") == "Mario_ Juve_Real_.fmsa"
    with pytest.raises(ValueError):
        career_file_name("  ..  ")


def test_list_saves(setup) -> None:  # type: ignore[no-untyped-def]
    client, _, saves = setup
    r = client.get("/api/saves", headers=H).json()
    assert r["folder"] == str(saves)
    assert [s["name"] for s in r["saves"]] == ["Mario - Juventus"]


def test_careers_list_detail_and_open(setup) -> None:  # type: ignore[no-untyped-def]
    client, store, _ = setup
    path = Path(store.get().careers_dir) / "Mario.fmsa"
    make_career(path, "Mario - Juventus")
    careers = client.get("/api/careers", headers=H).json()
    assert [(c["name"], c["imports"], c["manager"]) for c in careers] == [
        ("Mario - Juventus", 1, "Mario")
    ]
    detail = client.get("/api/careers/detail", params={"path": str(path)}, headers=H).json()
    assert detail["imports"][0]["skipped_readers"][0]["reader"] == "officials"
    assert client.post("/api/careers/open", json={"path": str(path)}, headers=H).status_code == 200
    assert store.get().last_career == str(path)
    assert store.get().recent_careers == [str(path)]


def test_create_rejects_existing_and_missing(setup) -> None:  # type: ignore[no-untyped-def]
    client, store, saves = setup
    make_career(Path(store.get().careers_dir) / "Mario.fmsa", "Mario")
    save = str(saves / "Mario - Juventus.fm")
    r = client.post("/api/careers", json={"name": "Mario", "save_path": save}, headers=H)
    assert r.status_code == 409
    r = client.post("/api/careers", json={"name": "X", "save_path": "C:/nope.fm"}, headers=H)
    assert r.status_code == 404


def test_create_with_invalid_save_fails_cleanly(setup) -> None:  # type: ignore[no-untyped-def]
    client, store, saves = setup
    save = str(saves / "Mario - Juventus.fm")  # not a real save
    job = client.post("/api/careers", json={"name": "New", "save_path": save}, headers=H).json()
    import time

    for _ in range(100):
        job = client.get(f"/api/jobs/{job['id']}", headers=H).json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "failed"
    assert not (Path(store.get().careers_dir) / "New.fmsa").exists()
