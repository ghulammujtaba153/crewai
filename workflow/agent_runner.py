"""Lightweight agent runner for the heal loop (fewer LLM round-trips)."""

from __future__ import annotations

import re
import time

from crewai import Crew, Process, Task
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config import require_groq_key, resolve_groq_model, GROQ_AGENT_MODEL


def _chat() -> ChatGroq:
    return ChatGroq(
        api_key=require_groq_key(),
        model=resolve_groq_model(GROQ_AGENT_MODEL),
        temperature=0.1,
        timeout=120,
    )


def _retry_delay(exc: Exception, attempt: int) -> float:
    match = re.search(r"try again in ([\d.]+)s", str(exc), re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return float(2**attempt)


def summarize(role: str, instructions: str, context: str) -> str:
    """Single-shot Groq summary for heal-loop nodes."""
    llm = _chat()
    system = (
        f"You are Sentinel's {role}. Use only the MCP gateway context provided. "
        "Be concise and actionable. Do not invent hosts or metrics."
    )
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            result = llm.invoke(
                [
                    SystemMessage(content=system),
                    HumanMessage(content=f"{instructions}\n\n{context}"),
                ]
            )
            text = getattr(result, "content", str(result))
            if text and str(text).strip():
                return str(text).strip()
            raise RuntimeError("Empty LLM response")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            msg = str(exc).lower()
            if any(x in msg for x in ("rate limit", "disconnect", "timeout", "502", "503")):
                if attempt < 3:
                    time.sleep(_retry_delay(exc, attempt))
                    continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("summarize failed")


def run_crew_task(agent, description: str, expected_output: str) -> str:
    """Full CrewAI path (used for NL2SQL)."""
    task = Task(description=description, expected_output=expected_output, agent=agent)
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            return str(crew.kickoff())
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            msg = str(exc).lower()
            if any(
                x in msg
                for x in ("rate limit", "disconnect", "timeout", "internalservererror")
            ) and attempt < 3:
                time.sleep(_retry_delay(exc, attempt))
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("crew task failed")
