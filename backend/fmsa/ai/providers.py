"""Adapters for the three AI providers, behind one small interface.

Each adapter keeps the conversation in its provider's native format (so, for Claude, assistant
content such as thinking blocks is sent back unchanged) and exposes:

    add_user(text) / step() -> Step / add_tool_results(results) / list_models()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from fmsa.ai.tools import TOOLS

DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "", "gemini": ""}
# Claude models that accept the server-side refusal fallback ("default" routing).
CLAUDE_FALLBACK_MODELS = {
    "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1",
}  # fmt: skip
MAX_TOKENS = 16_000


class ProviderError(Exception):
    """A provider call failed; the message is safe to show to the user."""


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(slots=True)
class ToolResult:
    call: ToolCall
    text: str
    is_error: bool = False


@dataclass(slots=True)
class Step:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class Provider:
    name = ""

    def __init__(self, api_key: str, model: str, system: str) -> None:
        self.api_key = api_key
        self.model = model or DEFAULT_MODELS[self.name]
        if not self.model:
            raise ProviderError("Choose a model for this provider in Settings.")
        self.system = system

    def add_user(self, text: str) -> None:
        raise NotImplementedError

    def step(self) -> Step:
        raise NotImplementedError

    def add_tool_results(self, results: list[ToolResult]) -> None:
        raise NotImplementedError

    def list_models(self) -> list[str]:
        raise NotImplementedError


# ---------------------------------------------------------------------------- Anthropic


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, system: str) -> None:
        super().__init__(api_key, model, system)
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.messages: list[dict[str, Any]] = []
        self.tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["schema"],
                **({"strict": True} if t["schema"].get("additionalProperties") is False else {}),
            }
            for t in TOOLS
        ]

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def step(self) -> Step:
        a = self._anthropic
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": self.system,
            "tools": self.tools,
            "messages": self.messages,
        }
        if self.model in CLAUDE_FALLBACK_MODELS:
            # Re-run on a fallback model if a safety classifier declines the request.
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        try:
            response = self.client.beta.messages.create(**kwargs)
        except a.AuthenticationError as exc:
            raise ProviderError("Invalid Anthropic API key.") from exc
        except a.NotFoundError as exc:
            raise ProviderError(f"Model not found: {self.model}") from exc
        except a.RateLimitError as exc:
            raise ProviderError("Rate limited by Anthropic: retry in a minute.") from exc
        except a.APIStatusError as exc:
            raise ProviderError(f"Anthropic error {exc.status_code}: {exc.message}") from exc
        except a.APIConnectionError as exc:
            raise ProviderError("Cannot reach Anthropic: check the internet connection.") from exc

        step = Step(
            stop=str(response.stop_reason),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )
        if response.stop_reason == "refusal":
            step.text = "The model declined to answer this request."
            return step
        # keep the full assistant content (thinking, tool_use, ...) for the next request
        self.messages.append({"role": "assistant", "content": response.content})
        step.text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        step.tool_calls = [
            ToolCall(b.id, b.name, dict(b.input or {}))
            for b in response.content
            if b.type == "tool_use"
        ]
        if response.stop_reason == "max_tokens" and not step.tool_calls:
            step.text += "\n\n[...]"
        return step

    def add_tool_results(self, results: list[ToolResult]) -> None:
        self.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": r.call.id,
                        "content": r.text,
                        **({"is_error": True} if r.is_error else {}),
                    }
                    for r in results
                ],
            }
        )

    def list_models(self) -> list[str]:
        try:
            return [m.id for m in self.client.models.list(limit=100)]
        except self._anthropic.APIError as exc:
            raise ProviderError(str(exc)) from exc


# ---------------------------------------------------------------------------- OpenAI


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, api_key: str, model: str, system: str) -> None:
        super().__init__(api_key, model, system)
        import openai

        self._openai = openai
        self.client = openai.OpenAI(api_key=api_key)
        self.messages: list[Any] = [{"role": "system", "content": system}]
        self.tools: list[Any] = [
            {"type": "function",
             "function": {"name": t["name"], "description": t["description"],
                          "parameters": t["schema"]}}
            for t in TOOLS
        ]  # fmt: skip

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def step(self) -> Step:
        o = self._openai
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=self.messages, tools=self.tools
            )
        except o.AuthenticationError as exc:
            raise ProviderError("Invalid OpenAI API key.") from exc
        except o.NotFoundError as exc:
            raise ProviderError(f"Model not found: {self.model}") from exc
        except o.RateLimitError as exc:
            raise ProviderError("Rate limited by OpenAI: retry in a minute.") from exc
        except o.APIStatusError as exc:
            raise ProviderError(f"OpenAI error {exc.status_code}: {exc.message}") from exc
        except o.APIConnectionError as exc:
            raise ProviderError("Cannot reach OpenAI: check the internet connection.") from exc
        choice = response.choices[0]
        msg = choice.message
        calls: list[ChatCompletionMessageFunctionToolCall] = [
            c for c in msg.tool_calls or [] if isinstance(c, ChatCompletionMessageFunctionToolCall)
        ]
        entry: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if calls:
            entry["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in calls
            ]  # fmt: skip
        self.messages.append(entry)
        tool_calls = []
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(c.id, c.function.name, args))
        usage = response.usage
        return Step(
            text=(msg.content or "").strip(),
            tool_calls=tool_calls,
            stop=str(choice.finish_reason),
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
        )

    def add_tool_results(self, results: list[ToolResult]) -> None:
        for r in results:
            self.messages.append({"role": "tool", "tool_call_id": r.call.id, "content": r.text})

    def list_models(self) -> list[str]:
        try:
            return sorted(m.id for m in self.client.models.list())
        except self._openai.APIError as exc:
            raise ProviderError(str(exc)) from exc


# ---------------------------------------------------------------------------- Gemini


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, system: str) -> None:
        super().__init__(api_key, model, system)
        from google import genai
        from google.genai import errors, types

        self._types = types
        self._errors = errors
        self.client = genai.Client(api_key=api_key)
        self.contents: list[Any] = []
        self.config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t["name"],
                            description=t["description"],
                            parameters_json_schema=t["schema"],
                        )
                        for t in TOOLS
                    ]
                )
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def add_user(self, text: str) -> None:
        t = self._types
        self.contents.append(t.Content(role="user", parts=[t.Part(text=text)]))

    def step(self) -> Step:
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=self.contents, config=self.config
            )
        except self._errors.APIError as exc:
            if exc.code in (401, 403):
                raise ProviderError("Invalid Gemini API key.") from exc
            if exc.code == 404:
                raise ProviderError(f"Model not found: {self.model}") from exc
            if exc.code == 429:
                raise ProviderError("Rate limited by Gemini: retry in a minute.") from exc
            raise ProviderError(f"Gemini error {exc.code}: {exc.message}") from exc
        except OSError as exc:
            raise ProviderError("Cannot reach Gemini: check the internet connection.") from exc
        candidate = response.candidates[0] if response.candidates else None
        if candidate is None or candidate.content is None:
            return Step(text="The model returned no answer.", stop="empty")
        self.contents.append(candidate.content)
        calls = [
            ToolCall(fc.id or f"call_{i}", fc.name or "", dict(fc.args or {}))
            for i, fc in enumerate(response.function_calls or [])
        ]
        text = "\n".join(p.text for p in candidate.content.parts or [] if p.text).strip()
        usage = response.usage_metadata
        return Step(
            text=text,
            tool_calls=calls,
            stop=str(candidate.finish_reason),
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            model=self.model,
        )

    def add_tool_results(self, results: list[ToolResult]) -> None:
        t = self._types
        parts = [
            t.Part(
                function_response=t.FunctionResponse(
                    id=r.call.id if not r.call.id.startswith("call_") else None,
                    name=r.call.name,
                    response={"error": r.text} if r.is_error else {"result": r.text},
                )
            )
            for r in results
        ]
        self.contents.append(t.Content(role="user", parts=parts))

    def list_models(self) -> list[str]:
        try:
            return sorted(
                (m.name or "").removeprefix("models/")
                for m in self.client.models.list()
                if "generateContent" in (m.supported_actions or [])
            )
        except self._errors.APIError as exc:
            raise ProviderError(str(exc)) from exc


PROVIDERS: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}
