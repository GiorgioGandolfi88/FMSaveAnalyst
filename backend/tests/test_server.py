from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fmsa import __version__
from fmsa.config import Settings, SettingsStore
from fmsa.paths import PORTABLE_FLAG, AppPaths
from fmsa.server import TOKEN_HEADER, create_app

TOKEN = "test-token"


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / PORTABLE_FLAG).touch()
    dist = tmp_path / "bundle" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    p = AppPaths.resolve(app_dir=app_dir, bundle_dir=tmp_path / "bundle")
    p.ensure()
    return p


@pytest.fixture
def client(paths: AppPaths) -> TestClient:
    app = create_app(paths, SettingsStore(paths), TOKEN)
    return TestClient(app, base_url="http://127.0.0.1")


def auth() -> dict[str, str]:
    return {TOKEN_HEADER: TOKEN}


def test_portable_mode_keeps_data_next_to_app(paths: AppPaths) -> None:
    assert paths.portable
    assert paths.data_dir == paths.app_dir / "data"


def test_non_portable_uses_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    p = AppPaths.resolve(app_dir=tmp_path, bundle_dir=tmp_path)
    assert not p.portable
    assert p.data_dir == tmp_path / "roaming" / "FMSaveAnalyst"


def test_api_requires_token(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/health", headers={TOKEN_HEADER: "wrong"}).status_code == 401
    r = client.get("/api/health", headers=auth())
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": __version__}


def test_foreign_host_rejected(paths: AppPaths) -> None:
    app = create_app(paths, SettingsStore(paths), TOKEN)
    evil = TestClient(app, base_url="http://evil.example")
    assert evil.get("/api/health", headers=auth()).status_code == 400


def test_settings_defaults_and_roundtrip(client: TestClient, paths: AppPaths) -> None:
    s = Settings.model_validate(client.get("/api/settings", headers=auth()).json())
    assert s.language == "it"
    assert s.masking.potential_ability is True
    assert s.careers_dir == str(paths.data_dir / "careers")
    assert s.reference_db == str(paths.app_dir / "reference" / "fm_reference.sqlite")

    s.language = "en"
    s.masking.current_ability = True
    r = client.put("/api/settings", headers=auth(), json=s.model_dump())
    assert r.status_code == 200
    reloaded = SettingsStore(paths).get()
    assert reloaded.language == "en"
    assert reloaded.masking.current_ability is True


def test_invalid_settings_rejected(client: TestClient) -> None:
    body = Settings().model_dump()
    body["language"] = "de"
    assert client.put("/api/settings", headers=auth(), json=body).status_code == 422


def test_corrupt_settings_file_is_set_aside(paths: AppPaths) -> None:
    paths.settings_file.write_text("{not json", encoding="utf-8")
    store = SettingsStore(paths)
    assert store.get().language == "it"
    assert paths.settings_file.with_suffix(".invalid.json").exists()


def test_frontend_served_without_token(client: TestClient) -> None:
    assert client.get("/").text == "<html>index</html>"
    assert client.get("/some/route").text == "<html>index</html>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/../pyproject.toml").text == "<html>index</html>"
