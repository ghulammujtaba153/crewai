"""MCP tool implementations. Agents must use these as the only system interface."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langsmith import traceable

from config import (
    ALLOWED_COMMANDS,
    ALLOWED_TABLES,
    CRITICAL_DB_LOAD,
    DB_PATH,
    HIGH_RISK_COMMANDS,
    KB_PATH,
    SCHEMA_DESCRIPTION,
    configure_langsmith,
    require_groq_key,
    resolve_groq_model,
)

configure_langsmith()

_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|TRUNCATE)\b",
    re.IGNORECASE,
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run: python main.py init-db"
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=require_groq_key(),
        model=resolve_groq_model(),
        temperature=0,
    )


def get_unhealthy_servers() -> list[dict[str, Any]]:
    """Return servers currently in critical or degraded status."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT hostname, status, cpu_pct, db_load FROM servers "
            "WHERE status IN ('critical', 'degraded')"
        ).fetchall()
    return [dict(r) for r in rows]


@traceable(name="get_system_logs", run_type="tool")
def get_system_logs(
    level: str | None = None,
    server_id: int | None = None,
    limit: int = 20,
) -> str:
    """Return recent system logs from the telemetry database."""
    limit = max(1, min(int(limit), 100))
    clauses: list[str] = []
    params: list[Any] = []

    if level:
        clauses.append("UPPER(level) = UPPER(?)")
        params.append(level)
    if server_id is not None:
        clauses.append("server_id = ?")
        params.append(int(server_id))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT id, server_id, timestamp, level, message, service "
        f"FROM logs {where} ORDER BY timestamp DESC LIMIT ?"
    )
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        return "No logs found for the given filters."

    lines = [
        f"[{r['timestamp']}] server={r['server_id']} {r['level']} "
        f"({r['service']}): {r['message']}"
        for r in rows
    ]
    return "\n".join(lines)


def _max_db_load() -> float:
    with _connect() as conn:
        row = conn.execute("SELECT MAX(db_load) AS m FROM servers").fetchone()
    return float(row["m"] if row and row["m"] is not None else 0.0)


@traceable(name="execute_system_command", run_type="tool")
def execute_system_command(command: str, target: str | None = None) -> str:
    """
    Simulate a read-only/safe system command.

    High-risk commands are blocked when database load is critical.
    """
    cmd = (command or "").strip().lower().replace(" ", "_")
    if not cmd:
        return "ERROR: No command provided."

    if cmd not in ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(ALLOWED_COMMANDS))
        return (
            f"ERROR: Command '{cmd}' is not in the simulated allowlist. "
            f"Allowed: {allowed}"
        )

    db_load = _max_db_load()
    if cmd in HIGH_RISK_COMMANDS and db_load >= CRITICAL_DB_LOAD:
        return (
            f"BLOCKED by safety guardrail: '{cmd}' is high-risk and current "
            f"max db_load is {db_load:.1f}% (threshold {CRITICAL_DB_LOAD}%). "
            "Suggested safer alternatives: clear_cache, scale_up, flush_connections, "
            "restart_service."
        )

    target_note = f" on target '{target}'" if target else ""
    effects = {
        "restart_service": "Service process recycled; memory pressure should ease.",
        "clear_cache": "Application/cache tier flushed; DB read pressure may drop.",
        "scale_up": "Additional capacity provisioned (simulated).",
        "flush_connections": "Idle connections recycled (simulated).",
        "rotate_logs": "Log files rotated (simulated).",
        "system_reboot": "Host reboot scheduled (simulated).",
        "force_kill_db": "Database process kill requested (simulated).",
        "drop_connections": "All DB connections dropped (simulated).",
        "shutdown_cluster": "Cluster shutdown requested (simulated).",
    }
    effect = effects.get(cmd, "Command acknowledged (simulated).")
    heal_note = _simulate_heal(cmd)
    return (
        f"OK: Executed '{cmd}'{target_note}. {effect} "
        f"(current max db_load={db_load:.1f}%){heal_note}"
    )


def _simulate_heal(command: str) -> str:
    """Apply simulated telemetry improvements after successful safe remediation."""
    safe = {"restart_service", "clear_cache", "scale_up", "flush_connections", "rotate_logs"}
    if command not in safe:
        return ""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE servers
            SET status = 'healthy',
                cpu_pct = MIN(cpu_pct, 55.0),
                mem_pct = MIN(mem_pct, 60.0),
                db_load = MIN(db_load, 45.0)
            WHERE status IN ('critical', 'degraded')
            """
        )
        conn.execute(
            """
            UPDATE incidents
            SET status = 'investigating'
            WHERE status = 'open' AND severity IN ('high', 'critical')
            """
        )
        conn.commit()
    return " Telemetry updated: critical/degraded hosts moved toward healthy."


def _load_kb_documents() -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    if not KB_PATH.exists():
        return docs
    for path in sorted(KB_PATH.glob("*.md")):
        docs.append((path.name, path.read_text(encoding="utf-8")))
    return docs


def _score_doc(query: str, text: str) -> float:
    tokens = {t.lower() for t in re.findall(r"[a-zA-Z0-9_]+", query) if len(t) > 2}
    if not tokens:
        return 0.0
    text_l = text.lower()
    hits = sum(1 for t in tokens if t in text_l)
    return hits / len(tokens)


@traceable(name="query_knowledge_base", run_type="tool")
def query_knowledge_base(query: str, top_k: int = 2) -> str:
    """Retrieve relevant runbook passages from the knowledge base (lightweight RAG)."""
    docs = _load_kb_documents()
    if not docs:
        return "Knowledge base is empty. Add markdown runbooks under data/knowledge_base/."

    ranked = sorted(
        ((name, text, _score_doc(query, text)) for name, text in docs),
        key=lambda x: x[2],
        reverse=True,
    )
    top_k = max(1, min(int(top_k), 5))
    selected = [r for r in ranked[:top_k] if r[2] > 0] or ranked[:1]

    parts = []
    for name, text, score in selected:
        parts.append(f"### Source: {name} (relevance={score:.2f})\n{text.strip()}")
    return "\n\n".join(parts)


def _extract_sql(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence:
        return fence.group(1).strip().rstrip(";")
    # Single-line SQL
    for line in text.splitlines():
        if line.strip().upper().startswith("SELECT"):
            return line.strip().rstrip(";")
    return text.strip().rstrip(";")


def _validate_sql(sql: str) -> str | None:
    """Return an error message if SQL is unsafe/out-of-scope, else None."""
    if not sql:
        return "Empty SQL."
    if sql.upper().startswith("OUT_OF_SCOPE"):
        return "OUT_OF_SCOPE"
    if not sql.upper().lstrip().startswith("SELECT"):
        return "Only SELECT queries are permitted."
    if _FORBIDDEN_SQL.search(sql):
        return "Forbidden SQL keyword detected."
    if ";" in sql:
        return "Multiple statements are not allowed."

    # Table allowlist: any identifier after FROM/JOIN
    tables = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.I)
    if not tables:
        return "Could not identify target tables."
    for table in tables:
        if table.lower() not in ALLOWED_TABLES:
            return f"Table '{table}' is outside the allowed schema."
    return None


@traceable(name="nl2sql_generate", run_type="llm")
def _generate_sql(nl_query: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You translate natural language into SQLite SELECT queries.\n"
                "You may ONLY use this schema:\n{schema}\n\n"
                "Rules:\n"
                "1. Output ONLY a single SELECT statement, or the exact token OUT_OF_SCOPE.\n"
                "2. If the question cannot be answered from the schema "
                "(e.g. personal opinions, unrelated facts), output OUT_OF_SCOPE.\n"
                "3. Never invent columns or tables.\n"
                "4. No comments, no markdown, no explanation.",
            ),
            ("human", "{question}"),
        ]
    )
    chain = prompt | _llm()
    result = chain.invoke({"schema": SCHEMA_DESCRIPTION, "question": nl_query})
    content = result.content if hasattr(result, "content") else str(result)
    return str(content).strip()


@traceable(name="query_database", run_type="tool")
def query_database(nl_query: str) -> str:
    """
    Translate a natural-language question into SQL, validate, and execute.

    Gracefully refuses questions outside the telemetry schema.
    """
    question = (nl_query or "").strip()
    if not question:
        return "Please provide a natural-language question about infrastructure health."

    try:
        raw = _generate_sql(question)
    except Exception as exc:  # noqa: BLE001
        return f"NL2SQL generation failed: {exc}"

    if "OUT_OF_SCOPE" in raw.upper():
        return (
            "I can only answer questions about infrastructure telemetry in this database "
            "(servers, logs, and incidents). Your question is outside that schema, "
            "so I cannot look it up or invent an answer."
        )

    sql = _extract_sql(raw)
    validation_error = _validate_sql(sql)
    if validation_error == "OUT_OF_SCOPE":
        return (
            "I can only answer questions about infrastructure telemetry in this database "
            "(servers, logs, and incidents). Your question is outside that schema, "
            "so I cannot look it up or invent an answer."
        )
    if validation_error:
        # Treat invalid/hallucinated SQL for unrelated questions as graceful degradation
        return (
            "I could not map that question to the telemetry schema "
            f"(servers, logs, incidents). Detail: {validation_error}. "
            "Please ask about infrastructure health metrics, logs, or incidents."
        )

    try:
        with _connect() as conn:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    except sqlite3.Error as exc:
        return f"SQL execution error: {exc}. Generated SQL was: {sql}"

    payload = {"nl_query": question, "sql": sql, "row_count": len(rows), "rows": rows}
    return json.dumps(payload, indent=2, default=str)
