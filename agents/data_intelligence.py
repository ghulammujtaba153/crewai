"""Data Intelligence Agent — NL2SQL interface over operational telemetry."""

from __future__ import annotations

from crewai import Agent

from agents.llm import build_nl2sql_llm
from tools.mcp_tools import get_mcp_tools


def build_data_intelligence_agent() -> Agent:
    return Agent(
        role="Data Intelligence Agent",
        goal=(
            "Answer natural-language questions about infrastructure health by querying "
            "the SQL telemetry database through the MCP query_database tool."
        ),
        backstory=(
            "You are Sentinel's Data Intelligence Interface. You never write SQL yourself "
            "for execution — you always call query_database with the user's natural "
            "language question. If the tool reports the question is out of scope, explain "
            "the limitation clearly and do not invent data."
        ),
        tools=get_mcp_tools(["query_database"]),
        llm=build_nl2sql_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=6,
        max_retry_limit=3,
    )
