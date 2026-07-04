"""Diagnostician Agent — uses RAG knowledge base to determine root causes."""

from __future__ import annotations

from crewai import Agent

from agents.llm import build_llm
from tools.mcp_tools import get_mcp_tools


def build_diagnostician_agent() -> Agent:
    return Agent(
        role="Diagnostician Agent",
        goal=(
            "Determine root causes of anomalies using the knowledge base (RAG) and "
            "supporting logs via the MCP gateway."
        ),
        backstory=(
            "You are Sentinel's Diagnostician. You consult operational runbooks through "
            "query_knowledge_base and corroborate with get_system_logs. You produce a "
            "concise root-cause analysis and recommended remediation direction. "
            "On retries, refine the diagnosis using prior verification feedback."
        ),
        tools=get_mcp_tools(["query_knowledge_base", "get_system_logs"]),
        llm=build_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=6,
        max_retry_limit=3,
    )
