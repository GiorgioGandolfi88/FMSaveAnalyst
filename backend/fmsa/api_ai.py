"""API routes: AI providers, keys and assistant conversations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fmsa.ai import keys
from fmsa.ai.agents import AGENTS
from fmsa.ai.chat import ChatManager
from fmsa.ai.providers import DEFAULT_MODELS, PROVIDERS, ProviderError
from fmsa.config import SettingsStore


class KeyBody(BaseModel):
    provider: str
    key: str


class ProviderBody(BaseModel):
    provider: str


class NewChat(BaseModel):
    agent: str = "general"


class MessageBody(BaseModel):
    text: str


class ApprovalBody(BaseModel):
    approve: bool


def create_router(store: SettingsStore, chats: ChatManager | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/ai")
    manager = chats or ChatManager()

    def provider_or_404(name: str) -> str:
        if name not in PROVIDERS:
            raise HTTPException(404, f"unknown provider {name}")
        return name

    @router.get("/status")
    def status() -> dict[str, Any]:
        s = store.get()
        return {
            "provider": s.ai.provider,
            "model": s.ai.model or DEFAULT_MODELS.get(s.ai.provider, ""),
            "confirm_before_send": s.ai.confirm_before_send,
            "keys": {p: keys.has_key(p) for p in PROVIDERS},
            "default_models": DEFAULT_MODELS,
            "agents": [
                {"id": a.id, "name": a.name, "description": a.description} for a in AGENTS.values()
            ],
        }

    @router.put("/key")
    def put_key(body: KeyBody) -> dict[str, bool]:
        try:
            keys.set_key(provider_or_404(body.provider), body.key)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"saved": True}

    @router.delete("/key/{provider}")
    def delete_key(provider: str) -> dict[str, bool]:
        keys.delete_key(provider_or_404(provider))
        return {"deleted": True}

    @router.post("/test")
    def test(body: ProviderBody) -> dict[str, Any]:
        name = provider_or_404(body.provider)
        key = keys.get_key(name)
        if not key:
            raise HTTPException(409, "no API key saved for this provider")
        try:
            models = PROVIDERS[name](key, DEFAULT_MODELS[name] or "test", "").list_models()
        except ProviderError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True, "models": models[:300]}

    @router.post("/chats")
    def new_chat(body: NewChat) -> dict[str, Any]:
        s = store.get()
        career = s.last_career
        if not career or not Path(career).is_file():
            raise HTTPException(409, "no career is open")
        provider = s.ai.provider
        if provider not in PROVIDERS:
            raise HTTPException(409, "choose an AI provider in Settings")
        key = keys.get_key(provider)
        if not key:
            raise HTTPException(409, "no API key saved for this provider")
        try:
            chat = manager.create(
                agent=body.agent,
                provider=provider,
                model=s.ai.model,
                api_key=key,
                career=Path(career),
                masking=s.masking,
                language=s.language,
                confirm=s.ai.confirm_before_send,
            )
        except ProviderError as exc:
            raise HTTPException(400, str(exc)) from exc
        return chat.to_dict()

    def chat_or_404(chat_id: str) -> Any:
        chat = manager.get(chat_id)
        if chat is None:
            raise HTTPException(404, "conversation not found (the app was restarted?)")
        return chat

    @router.get("/chats/{chat_id}")
    def get_chat(chat_id: str) -> dict[str, Any]:
        return chat_or_404(chat_id).to_dict()

    @router.post("/chats/{chat_id}/messages")
    def send(chat_id: str, body: MessageBody) -> dict[str, Any]:
        text = body.text.strip()
        if not text:
            raise HTTPException(422, "empty message")
        try:
            return manager.send(chat_or_404(chat_id), text).to_dict()
        except ProviderError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/chats/{chat_id}/approval")
    def approval(chat_id: str, body: ApprovalBody) -> dict[str, Any]:
        return manager.approve(chat_or_404(chat_id), body.approve).to_dict()

    @router.delete("/chats/{chat_id}")
    def close(chat_id: str) -> dict[str, bool]:
        manager.close(chat_id)
        return {"closed": True}

    return router
