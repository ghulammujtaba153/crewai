"""
MCP Server — standardized gateway for Sentinel agents.

Exposes:
  - get_system_logs
  - execute_system_command
  - query_knowledge_base
  - query_database
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.gateway import (  # noqa: E402
    execute_system_command as _execute_system_command,
    get_system_logs as _get_system_logs,
    query_database as _query_database,
    query_knowledge_base as _query_knowledge_base,
)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sentinel-gateway")


@mcp.tool()
def get_system_logs(
    level: str | None = None,
    server_id: int | None = None,
    limit: int = 20,
) -> str:
    """Parse and return system logs/telemetry entries. Optional filters: level, server_id, limit."""
    return _get_system_logs(level=level, server_id=server_id, limit=limit)


@mcp.tool()
def execute_system_command(command: str, target: str | None = None) -> str:
    """Execute a simulated/read-only system command. High-risk commands are blocked under critical DB load."""
    return _execute_system_command(command=command, target=target)


@mcp.tool()
def query_knowledge_base(query: str, top_k: int = 2) -> str:
    """Query the operational knowledge base (RAG runbooks) for root-cause guidance."""
    return _query_knowledge_base(query=query, top_k=top_k)


@mcp.tool()
def query_database(nl_query: str) -> str:
    """Answer natural-language questions about infrastructure health via NL2SQL against system_telemetry.db."""
    return _query_database(nl_query=nl_query)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
