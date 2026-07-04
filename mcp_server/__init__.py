"""MCP gateway package — sole entry point for system interaction."""

from mcp_server.gateway import (
    execute_system_command,
    get_system_logs,
    query_database,
    query_knowledge_base,
)

__all__ = [
    "get_system_logs",
    "execute_system_command",
    "query_knowledge_base",
    "query_database",
]
