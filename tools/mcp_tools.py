"""
CrewAI tools backed by the MCP gateway implementations.

Agents must not access the database, filesystem, or shell directly —
only through these tools (same surface as the MCP server).
"""

from __future__ import annotations

from crewai.tools import tool

from mcp_server.gateway import (
    execute_system_command as _execute_system_command,
    get_system_logs as _get_system_logs,
    query_database as _query_database,
    query_knowledge_base as _query_knowledge_base,
)


@tool("get_system_logs")
def get_system_logs_tool(
    level: str = "",
    server_id: str = "",
    limit: str = "20",
) -> str:
    """Fetch recent system logs. Optional level (ERROR/WARN/INFO/CRITICAL), server_id, and limit."""
    sid = int(server_id) if str(server_id).strip().isdigit() else None
    try:
        lim = int(limit) if str(limit).strip() else 20
    except ValueError:
        lim = 20
    return _get_system_logs(
        level=level or None,
        server_id=sid,
        limit=lim,
    )


@tool("execute_system_command")
def execute_system_command_tool(command: str, target: str = "") -> str:
    """Run a simulated system command (restart_service, clear_cache, scale_up, etc.)."""
    return _execute_system_command(command=command, target=target or None)


@tool("query_knowledge_base")
def query_knowledge_base_tool(query: str) -> str:
    """Retrieve runbooks and root-cause guidance from the knowledge base (RAG)."""
    return _query_knowledge_base(query=query)


@tool("query_database")
def query_database_tool(nl_query: str) -> str:
    """Answer natural-language questions about infrastructure health using NL2SQL."""
    return _query_database(nl_query=nl_query)


def get_mcp_tools(names: list[str] | None = None) -> list:
    """Return MCP-backed CrewAI tools, optionally filtered by name."""
    catalog = {
        "get_system_logs": get_system_logs_tool,
        "execute_system_command": execute_system_command_tool,
        "query_knowledge_base": query_knowledge_base_tool,
        "query_database": query_database_tool,
    }
    if names is None:
        return list(catalog.values())
    return [catalog[n] for n in names if n in catalog]
