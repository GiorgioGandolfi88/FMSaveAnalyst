"""API keys in the Windows Credential Manager (DPAPI-encrypted), never in settings or databases."""

from __future__ import annotations

import contextlib
import logging

import keyring
import keyring.errors

log = logging.getLogger(__name__)

SERVICE = "FMSaveAnalyst"
PROVIDERS = ("anthropic", "openai", "gemini")


def _check(provider: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider}")


def get_key(provider: str) -> str | None:
    _check(provider)
    try:
        return keyring.get_password(SERVICE, provider)
    except keyring.errors.KeyringError:
        log.exception("Credential store unavailable")
        return None


def set_key(provider: str, key: str) -> None:
    _check(provider)
    key = key.strip()
    if not key:
        raise ValueError("empty key")
    keyring.set_password(SERVICE, provider, key)


def delete_key(provider: str) -> None:
    _check(provider)
    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(SERVICE, provider)


def has_key(provider: str) -> bool:
    return bool(get_key(provider))
