"""Remediation Agent — proposes/executes fixes and respects safety guardrails."""

from __future__ import annotations

from crewai import Agent

from agents.llm import build_llm
from tools.mcp_tools import get_mcp_tools


def build_remediation_agent() -> Agent:
    return Agent(
        role="Remediation Agent",
        goal=(
            "Propose and execute safe remediation commands through the MCP gateway, "
            "avoiding high-risk actions under critical database load."
        ),
        backstory=(
            "You are Sentinel's Remediation specialist. You only use "
            "execute_system_command and get_system_logs via MCP. Prefer safe actions "
            "(clear_cache, scale_up, flush_connections, restart_service). Never insist "
            "on system_reboot or force_kill_db when the gateway reports a safety block. "
            "Report exactly what was executed and any guardrail blocks."
        ),
        tools=get_mcp_tools(["execute_system_command", "get_system_logs"]),
        llm=build_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=6,
        max_retry_limit=3,
    )
