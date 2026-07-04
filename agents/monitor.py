"""Monitor Agent — parses logs and telemetry to detect anomalies."""

from __future__ import annotations

from crewai import Agent

from agents.llm import build_llm
from tools.mcp_tools import get_mcp_tools


def build_monitor_agent() -> Agent:
    return Agent(
        role="Monitor Agent",
        goal=(
            "Detect infrastructure anomalies by inspecting system logs and telemetry "
            "through the MCP gateway only."
        ),
        backstory=(
            "You are Sentinel's front-line Monitor. You never access databases or hosts "
            "directly — only via MCP tools get_system_logs and query_database. "
            "You summarize clear, actionable anomalies (host, severity, evidence)."
        ),
        tools=get_mcp_tools(["get_system_logs", "query_database"]),
        llm=build_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=6,
        max_retry_limit=3,
    )
