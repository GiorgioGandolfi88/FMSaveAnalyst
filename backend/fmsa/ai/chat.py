"""Conversations with the assistants: the agent loop, local tool execution and the approval gate.

When "ask before sending data" is on, every batch of tool results is shown to the user first; the
loop pauses (status "needs_approval") and resumes only after the user approves or declines. A
declined result is replaced by a short note, so the model knows the data was withheld.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fmsa.ai.agents import AGENTS, system_prompt
from fmsa.ai.providers import PROVIDERS, Provider, ProviderError, ToolResult
from fmsa.ai.tools import ToolRunner
from fmsa.config import MaskingSettings
from fmsa.query.session import QueryError, ReadOnlySession, open_career

log = logging.getLogger(__name__)

MAX_STEPS = 12
DECLINED = "The user chose not to share this data. Continue without it or ask for something else."
LANGUAGES = {"it": "Italian", "en": "English"}


@dataclass
class ChatSession:
    id: str
    agent: str
    provider_name: str
    model: str
    career: Path
    confirm: bool
    provider: Provider
    tools: ToolRunner
    db: ReadOnlySession
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "idle"  # idle | needs_approval
    pending: list[ToolResult] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    sent_chars: int = 0
    created: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "provider": self.provider_name,
            "model": self.provider.model,
            "confirm": self.confirm,
            "status": self.status,
            "events": self.events,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "sent_chars": self.sent_chars,
            },
        }


def _context(db: ReadOnlySession, masking: MaskingSettings, language: str) -> dict[str, str]:
    def one(sql: str) -> Any:
        try:
            rows = db.query(sql, limit=1).rows
            return rows[0][0] if rows else None
        except QueryError:
            return None

    hidden = [
        label
        for flag, label in (
            (masking.potential_ability, "potential ability (ability_potential)"),
            (masking.current_ability, "current ability (ability_current)"),
            (masking.hidden_attributes, "hidden attributes (consistency, important matches, ...)"),
            (masking.personality, "personality (personality_*)"),
        )
        if flag
    ] + list(masking.extra_columns)
    managed = one("SELECT club_name || ' (club_uid ' || club_uid || ')' FROM managed_clubs")
    return {
        "career_name": one("SELECT value FROM _meta WHERE key = 'career_name'") or "career",
        "game": one("SELECT value FROM _meta WHERE key = 'game'") or "Football Manager",
        "today": one("SELECT max(game_date) FROM _imports WHERE status = 'ok'") or "unknown",
        "managed": f"The user manages {managed}." if managed else "The user manages no club now.",
        "masked": ", ".join(hidden) if hidden else "none",
        "language": LANGUAGES.get(language, "the user's language"),
    }


class ChatManager:
    def __init__(self) -> None:
        self.sessions: dict[str, ChatSession] = {}

    def create(
        self,
        *,
        agent: str,
        provider: str,
        model: str,
        api_key: str,
        career: Path,
        masking: MaskingSettings,
        language: str,
        confirm: bool,
    ) -> ChatSession:
        if agent not in AGENTS:
            raise ProviderError(f"unknown assistant {agent}")
        if provider not in PROVIDERS:
            raise ProviderError("Choose an AI provider in Settings.")
        db = open_career(career, masking)
        prompt = system_prompt(AGENTS[agent], _context(db, masking, language))
        try:
            impl = PROVIDERS[provider](api_key, model, prompt)
        except ProviderError:
            db.close()
            raise
        session = ChatSession(
            id=uuid.uuid4().hex[:12],
            agent=agent,
            provider_name=provider,
            model=impl.model,
            career=career,
            confirm=confirm,
            provider=impl,
            tools=ToolRunner(career, db),
            db=db,
        )
        self.sessions[session.id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        return self.sessions.get(session_id)

    def close(self, session_id: str) -> None:
        s = self.sessions.pop(session_id, None)
        if s:
            s.db.close()

    # ------------------------------------------------------------------ conversation

    def send(self, s: ChatSession, text: str) -> ChatSession:
        with s.lock:
            if s.status == "needs_approval":
                raise ProviderError("Approve or decline the pending data first.")
            s.events.append({"type": "user", "text": text})
            s.provider.add_user(text)
            self._run(s)
        return s

    def approve(self, s: ChatSession, approved: bool) -> ChatSession:
        with s.lock:
            if s.status != "needs_approval":
                return s
            results = s.pending if approved else [
                ToolResult(r.call, DECLINED, False) for r in s.pending
            ]  # fmt: skip
            for e in s.events:
                if e.get("type") == "tool" and e.get("status") == "pending":
                    e["status"] = "sent" if approved else "declined"
            s.pending = []
            s.status = "idle"
            self._send_results(s, results)
            self._run(s)
        return s

    def _send_results(self, s: ChatSession, results: list[ToolResult]) -> None:
        s.sent_chars += sum(len(r.text) for r in results)
        s.provider.add_tool_results(results)

    def _run(self, s: ChatSession) -> None:
        for _ in range(MAX_STEPS):
            try:
                step = s.provider.step()
            except ProviderError as exc:
                s.events.append({"type": "error", "text": str(exc)})
                return
            except Exception as exc:  # unexpected SDK failure: keep the session usable
                log.exception("AI step failed")
                s.events.append({"type": "error", "text": f"{type(exc).__name__}: {exc}"})
                return
            s.input_tokens += step.input_tokens
            s.output_tokens += step.output_tokens
            if step.text:
                s.events.append({"type": "assistant", "text": step.text})
            if not step.tool_calls:
                return
            results: list[ToolResult] = []
            for call in step.tool_calls:
                text, is_error, preview = s.tools.run(call.name, call.args)
                results.append(ToolResult(call, text, is_error))
                s.events.append(
                    {
                        "type": "tool",
                        "id": call.id,
                        "name": call.name,
                        "args": call.args,
                        "preview": preview,
                        "chars": len(text),
                        "status": "pending" if s.confirm else "sent",
                        "error": is_error,
                    }
                )
            if s.confirm:
                s.pending = results
                s.status = "needs_approval"
                return
            self._send_results(s, results)
        s.events.append({"type": "error", "text": "Stopped after too many steps."})
