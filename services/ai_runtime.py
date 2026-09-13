"""
Smart BethG
AI Runtime

This module provides one provider-neutral interface for sending
messages to an AI model.

The application does not expose API keys to the frontend.

Environment variables supported:

    AI_API_KEY
    AI_BASE_URL
    AI_MODEL

OpenAI-compatible defaults are also recognised:

    OPENAI_API_KEY
    OPENAI_BASE_URL
    OPENAI_MODEL
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


SYSTEM_PROMPT = """
You are Smart BethG, an AI work assistant.

Your job is to help the user accomplish real work.

Be honest about what you have and have not actually done.

Do not claim that you searched the web, edited a file, executed
code, created an artifact, or completed an external action unless
the application actually performed that operation.

When a request requires tools that are not currently available,
explain the limitation clearly and suggest the next useful step.

Prefer practical, direct answers.

For software-development requests, reason about the project
structure, dependencies, implementation risks, testing and
verification.

For research requests, distinguish known information from
information that still needs external verification.

For consequential actions, do not silently assume permission.
"""


class AIRuntimeError(Exception):
    """Raised when the AI runtime cannot complete a request."""


class AIProviderNotConfigured(AIRuntimeError):
    """Raised when no usable AI provider credentials exist."""


def _get_env(*names: str) -> str | None:
    """
    Return the first non-empty environment variable.
    """

    for name in names:
        value = os.getenv(name)

        if value and value.strip():
            return value.strip()

    return None


def get_provider_config() -> dict[str, Any]:
    """
    Read provider configuration from environment variables.
    """

    api_key = _get_env(
        "AI_API_KEY",
        "OPENAI_API_KEY",
    )

    base_url = _get_env(
        "AI_BASE_URL",
        "OPENAI_BASE_URL",
    ) or DEFAULT_BASE_URL

    model = _get_env(
        "AI_MODEL",
        "OPENAI_MODEL",
    ) or DEFAULT_MODEL

    return {
        "configured": bool(api_key),
        "base_url": base_url.rstrip("/"),
        "model": model,
    }


def provider_status() -> dict[str, Any]:
    """
    Return safe provider information.

    API keys are deliberately never returned.
    """

    config = get_provider_config()

    return {
        "configured": config["configured"],
        "base_url": config["base_url"],
        "model": config["model"],
        "provider": (
            "openai-compatible"
            if config["configured"]
            else "not-configured"
        ),
    }


def _build_request_body(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
) -> dict[str, Any]:
    """
    Build an OpenAI-compatible chat-completion request.
    """

    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }


def _extract_text(data: dict[str, Any]) -> str:
    """
    Extract assistant text from an OpenAI-compatible response.
    """

    choices = data.get("choices")

    if not isinstance(choices, list) or not choices:
        raise AIRuntimeError(
            "The AI provider returned no choices."
        )

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise AIRuntimeError(
            "The AI provider returned an invalid choice."
        )

    message = first_choice.get("message")

    if not isinstance(message, dict):
        raise AIRuntimeError(
            "The AI provider returned no assistant message."
        )

    content = message.get("content")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []

        for item in content:
            if isinstance(item, dict):
                text = item.get("text")

                if isinstance(text, str):
                    text_parts.append(text)

        result = "\n".join(text_parts).strip()

        if result:
            return result

    raise AIRuntimeError(
        "The AI provider returned an empty response."
    )


def generate_response(
    user_message: str,
    history: list[dict[str, str]] | None = None,
    system_context: str | None = None,
    temperature: float = 0.2,
    timeout: int = 90,
) -> dict[str, Any]:
    """
    Send a user request to the configured AI provider.

    Returns a normalized response dictionary.
    """

    user_message = user_message.strip()

    if not user_message:
        raise ValueError(
            "user_message cannot be empty."
        )

    config = get_provider_config()

    api_key = _get_env(
        "AI_API_KEY",
        "OPENAI_API_KEY",
    )

    if not api_key:
        raise AIProviderNotConfigured(
            "No AI provider API key is configured. "
            "Set AI_API_KEY or OPENAI_API_KEY."
        )

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.strip(),
        }
    ]

    if system_context:
        messages.append(
            {
                "role": "system",
                "content": system_context.strip(),
            }
        )

    if history:
        for item in history:

            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content")

            if role not in {
                "user",
                "assistant",
                "system",
            }:
                continue

            if not isinstance(content, str):
                continue

            content = content.strip()

            if not content:
                continue

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    body = _build_request_body(
        messages=messages,
        model=config["model"],
        temperature=temperature,
    )

    payload = json.dumps(
        body
    ).encode("utf-8")

    endpoint = (
        f"{config['base_url']}/chat/completions"
    )

    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            raw_data = response.read()

    except urllib.error.HTTPError as exc:

        try:
            error_body = exc.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            error_body = ""

        raise AIRuntimeError(
            "AI provider returned HTTP "
            f"{exc.code}: {error_body[:1000]}"
        ) from exc

    except urllib.error.URLError as exc:

        raise AIRuntimeError(
            "Unable to connect to the AI provider: "
            f"{exc.reason}"
        ) from exc

    except TimeoutError as exc:

        raise AIRuntimeError(
            "The AI provider request timed out."
        ) from exc

    except Exception as exc:

        raise AIRuntimeError(
            "Unexpected AI provider error: "
            f"{exc}"
        ) from exc

    try:
        data = json.loads(
            raw_data.decode(
                "utf-8"
            )
        )

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:

        raise AIRuntimeError(
            "The AI provider returned invalid JSON."
        ) from exc

    text = _extract_text(data)

    return {
        "ok": True,
        "provider": "openai-compatible",
        "model": config["model"],
        "content": text,
    }
