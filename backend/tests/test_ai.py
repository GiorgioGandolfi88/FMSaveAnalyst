"""AI assistants without network: a scripted provider drives the loop."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, ClassVar

import keyring
import pytest
from fastapi.testclient import TestClient
from keyring.backend import KeyringBackend

from fmsa.ai import keys
from fmsa.ai import providers as prov
from fmsa.ai.chat import DECLINED, ChatManager
from fmsa.ai.providers import Provider, Step, ToolCall, ToolResult
from fmsa.config import MaskingSettings, SettingsStore
from fmsa.paths import PORTABLE_FLAG, AppPaths
from fmsa.server import TOKEN_HEADER, create_app

H = {TOKEN_HEADER: "t"}


class MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.store:
            raise keyring.errors.PasswordDeleteError("missing")
        del self.store[(service, username)]


@pytest.fixture(autouse=True)
def memory_keyring() -> MemoryKeyring:
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    return backend


class Scripted(Provider):
    """Asks for one SQL query, then answers with what it received."""

    name = "anthropic"
    instances: ClassVar[list[Scripted]] = []

    def __init__(self, api_key: str, model: str, system: str) -> None:
        super().__init__(api_key, model or "fake", system)
        self.received: list[ToolResult] = []
        self.turn = 0
        Scripted.instances.append(self)

    def add_user(self, text: str) -> None:
        self.turn = 0

    def step(self) -> Step:
        self.turn += 1
        if self.turn == 1:
            sql = "SELECT name, ability_potential FROM players ORDER BY uid"
            return Step(text="Let me check.", tool_calls=[ToolCall("c1", "run_sql",
                        {"sql": sql, "purpose": "test"})])  # fmt: skip
        return Step(text=f"Done: {self.received[-1].text[:80]}")

    def add_tool_results(self, results: list[ToolResult]) -> None:
        self.received.extend(results)


@pytest.fixture
def career(tmp_path: Path) -> Path:
    db = tmp_path / "c.fmsa"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE _meta (key PRIMARY KEY, value);
        INSERT INTO _meta VALUES ('career_name', 'Test'), ('game', 'FM26');
        CREATE TABLE _imports (import_id INTEGER PRIMARY KEY, game_date, status);
        INSERT INTO _imports VALUES (1, '2030-06-15', 'ok');
        CREATE TABLE _columns (table_name, column_name, sql_type, source_path, field_status,
                               position);
        INSERT INTO _columns VALUES ('players', 'ability_potential', 'INTEGER',
                                    'ability.potential', '', 0);
        CREATE TABLE players (uid, name, ability_potential);
        INSERT INTO players VALUES (1, 'Alpha', 190);
        """
    )
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> ChatManager:
    monkeypatch.setitem(prov.PROVIDERS, "anthropic", Scripted)
    monkeypatch.setattr("fmsa.ai.chat.PROVIDERS", prov.PROVIDERS)
    Scripted.instances.clear()
    return ChatManager()


def new_chat(manager: ChatManager, career: Path, confirm: bool) -> Any:
    return manager.create(agent="scout", provider="anthropic", model="", api_key="k",
                          career=career, masking=MaskingSettings(), language="it",
                          confirm=confirm)  # fmt: skip


def test_tool_results_are_masked_and_sent(manager: ChatManager, career: Path) -> None:
    chat = manager.send(new_chat(manager, career, confirm=False), "Who is good?")
    sent = json.loads(Scripted.instances[0].received[0].text)
    assert sent["rows"] == [["Alpha", None]]  # potential hidden from the model
    assert sent["hidden_columns"] == ["ability_potential"]
    kinds = [e["type"] for e in chat.events]
    assert kinds == ["user", "assistant", "tool", "assistant"]
    assert chat.events[2]["status"] == "sent"
    assert "Italian" in Scripted.instances[0].system and "Test" in Scripted.instances[0].system


def test_approval_gate(manager: ChatManager, career: Path) -> None:
    chat = manager.send(new_chat(manager, career, confirm=True), "Who is good?")
    assert chat.status == "needs_approval"
    assert Scripted.instances[0].received == []  # nothing left the PC yet
    assert chat.events[-1]["status"] == "pending"
    assert chat.events[-1]["preview"]["rows"] == [["Alpha", None]]
    chat = manager.approve(chat, approved=False)
    assert chat.status == "idle"
    assert Scripted.instances[0].received[0].text == DECLINED
    assert chat.events[2]["status"] == "declined"


def test_refuses_writes_through_tools(manager: ChatManager, career: Path) -> None:
    chat = new_chat(manager, career, confirm=False)
    text, is_error, _ = chat.tools.run("run_sql", {"sql": "DELETE FROM players", "purpose": "x"})
    assert is_error and "read-only" in text


def test_keys_and_api(career: Path, tmp_path: Path, memory_keyring: MemoryKeyring,
                      monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    keys.set_key("openai", "  sk-test  ")
    assert keys.get_key("openai") == "sk-test"
    assert memory_keyring.store[("FMSaveAnalyst", "openai")] == "sk-test"
    with pytest.raises(ValueError):
        keys.set_key("other", "x")

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / PORTABLE_FLAG).touch()
    paths = AppPaths.resolve(app_dir=app_dir, bundle_dir=tmp_path / "bundle")
    paths.ensure()
    store = SettingsStore(paths)
    s = store.get()
    ai = s.ai.model_copy(update={"provider": "anthropic"})
    store.save(s.model_copy(update={"last_career": str(career), "ai": ai}))
    monkeypatch.setitem(prov.PROVIDERS, "anthropic", Scripted)
    client = TestClient(create_app(paths, store, "t"), base_url="http://127.0.0.1")

    status = client.get("/api/ai/status", headers=H).json()
    assert status["keys"] == {"anthropic": False, "openai": True, "gemini": False}
    assert len(status["agents"]) == 6
    assert client.post("/api/ai/chats", json={"agent": "scout"}, headers=H).status_code == 409
    assert client.put("/api/ai/key", json={"provider": "anthropic", "key": "k"},
                      headers=H).status_code == 200  # fmt: skip
    settings_text = store.path.read_text(encoding="utf-8")
    assert "sk-test" not in settings_text and '"k"' not in settings_text

    chat = client.post("/api/ai/chats", json={"agent": "scout"}, headers=H).json()
    assert chat["confirm"] is True and chat["status"] == "idle"
    chat = client.post(f"/api/ai/chats/{chat['id']}/messages", json={"text": "hi"},
                       headers=H).json()  # fmt: skip
    assert chat["status"] == "needs_approval"
    blocked = client.post(f"/api/ai/chats/{chat['id']}/messages", json={"text": "again"},
                          headers=H)  # fmt: skip
    assert blocked.status_code == 409
    chat = client.post(f"/api/ai/chats/{chat['id']}/approval", json={"approve": True},
                       headers=H).json()  # fmt: skip
    assert chat["events"][-1]["text"].startswith("Done:")
    assert chat["usage"]["sent_chars"] > 0
    assert client.delete("/api/ai/key/anthropic", headers=H).json() == {"deleted": True}
    assert not keys.has_key("anthropic")


def test_provider_requires_model() -> None:
    with pytest.raises(prov.ProviderError):
        prov.OpenAIProvider("k", "", "system")
