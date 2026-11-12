from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from fmsa import updates


@pytest.mark.parametrize(
    ("candidate", "current", "newer"),
    [
        ("v0.2.0", "0.1.0", True),
        ("0.1.1", "0.1.0", True),
        ("v1.0.0", "0.9.9", True),
        ("v0.1.0", "0.1.0", False),
        ("v0.1.0", "0.2.0", False),
        ("v0.2.0-beta", "0.2.0", False),
        ("v0.2.0", "0.2.0-beta", True),
        ("nonsense", "0.1.0", False),
    ],
)
def test_is_newer(candidate: str, current: str, newer: bool) -> None:
    assert updates.is_newer(candidate, current) is newer


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        pass


def fake_urlopen(payload: Any) -> Any:
    def opener(request: Any, timeout: float) -> FakeResponse:
        assert request.full_url == updates.LATEST_URL
        assert "FMSaveAnalyst" in request.get_header("User-agent")
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(json.dumps(payload).encode())

    return opener


def test_check_finds_new_release(monkeypatch: pytest.MonkeyPatch) -> None:
    release = {
        "tag_name": "v0.3.0",
        "html_url": "https://github.com/x/y/releases/tag/v0.3.0",
        "body": "Novità",
        "published_at": "2026-12-01T10:00:00Z",
        "assets": [{"name": "FMSaveAnalyst-0.3.0-win64.zip", "browser_download_url": "u"}],
    }
    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen(release))
    info = updates.check(current="0.1.0")
    assert info.update_available and info.latest == "0.3.0"
    assert info.download_url == "u" and info.notes == "Novità"


@pytest.mark.parametrize(
    "payload",
    [
        urllib.error.HTTPError("u", 404, "not found", {}, None),  # type: ignore[arg-type]
        {"tag_name": "v9.0.0", "prerelease": True},
        {"tag_name": "v0.1.0"},
    ],
)
def test_no_update(monkeypatch: pytest.MonkeyPatch, payload: Any) -> None:
    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen(payload))
    info = updates.check(current="0.1.0")
    assert not info.update_available and info.error is None


def test_offline_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        updates.urllib.request, "urlopen", fake_urlopen(urllib.error.URLError("no network"))
    )
    info = updates.check(current="0.1.0")
    assert info.error == "offline" and not info.update_available
