"""Shared LLM configuration for CrewAI agents (Groq via LiteLLM)."""

from __future__ import annotations

import re
import time
from typing import Any

from crewai import LLM
from crewai.llms.cache import strip_cache_breakpoint

from config import (
    GROQ_AGENT_MODEL,
    GROQ_MODEL,
    require_groq_key,
    resolve_groq_model,
)

_TRANSIENT_MARKERS = (
    "server disconnected",
    "internalservererror",
    "timeout",
    "connection reset",
    "rate limit",
    "rate_limit",
    "503",
    "502",
)


def _retry_delay(exc: Exception, attempt: int) -> float:
    match = re.search(r"try again in ([\d.]+)s", str(exc), re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return float(2**attempt)


class GroqLLM(LLM):
    """CrewAI LLM wrapper tuned for Groq reliability."""

    def supports_function_calling(self) -> bool:
        # Groq + LiteLLM native tool calls are unstable; use ReAct text tool parsing.
        return False

    def _format_messages_for_provider(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        cleaned: list[dict[str, Any]] = []
        for msg in messages:
            copy = dict(msg)
            strip_cache_breakpoint(copy)
            cleaned.append(copy)
        return super()._format_messages_for_provider(cleaned)

    def _handle_non_streaming_response(self, params, callbacks=None, **kwargs):  # type: ignore[no-untyped-def]
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                return super()._handle_non_streaming_response(
                    params, callbacks=callbacks, **kwargs
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                msg = str(exc).lower()
                if any(marker in msg for marker in _TRANSIENT_MARKERS) and attempt < 3:
                    time.sleep(_retry_delay(exc, attempt))
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError("Groq LLM call failed without an exception")


def _make_groq_llm(model_env: str, temperature: float) -> LLM:
    require_groq_key()
    model_id = resolve_groq_model(model_env)
    return GroqLLM(
        model=f"groq/{model_id}",
        temperature=temperature,
        timeout=120,
    )


def build_llm(temperature: float = 0.1) -> LLM:
    """LLM for Monitor / Diagnose / Remediate agents (lighter TPM footprint)."""
    return _make_groq_llm(GROQ_AGENT_MODEL, temperature)


def build_nl2sql_llm(temperature: float = 0.0) -> LLM:
    """LLM for Data Intelligence / NL2SQL (user-selected model, e.g. GPT OSS 120B)."""
    return _make_groq_llm(GROQ_MODEL, temperature)
