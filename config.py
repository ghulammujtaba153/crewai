"""Central configuration for Sentinel v2.0."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

# Paths
DATA_DIR = ROOT_DIR / "data"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "system_telemetry.db"))
KB_PATH = Path(os.getenv("KB_PATH", DATA_DIR / "knowledge_base"))
CHROMA_DIR = DATA_DIR / "chroma_kb"

# LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Groq model id as used by the Groq API (see https://console.groq.com/docs/models)
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Smaller model for multi-agent heal loop (avoids GPT OSS 120B 8k TPM limits)
GROQ_AGENT_MODEL = os.getenv("GROQ_AGENT_MODEL", "llama-3.1-8b-instant")

# Normalize common .env values to Groq API model ids
GROQ_MODEL_ALIASES = {
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "openai/gpt-oss-120b": "openai/gpt-oss-120b",
    "openai/gpt-oss-20b": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant": "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile": "llama-3.1-70b-versatile",
    "gemma2-9b-it": "gemma2-9b-it",
}


def resolve_groq_model(model: str | None = None) -> str:
    """Return the Groq API model id (e.g. openai/gpt-oss-120b)."""
    raw = (model or GROQ_MODEL or "").strip()
    if raw.startswith("groq/"):
        raw = raw[len("groq/") :]
    key = raw.lower().replace(" ", "-")
    if key in GROQ_MODEL_ALIASES:
        return GROQ_MODEL_ALIASES[key]
    if raw in GROQ_MODEL_ALIASES:
        return GROQ_MODEL_ALIASES[raw]
    # Pass through valid-looking Groq ids (provider/model or plain model name)
    if raw:
        return raw
    return "openai/gpt-oss-120b"

# Workflow
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
CRITICAL_DB_LOAD = float(os.getenv("CRITICAL_DB_LOAD", "80"))

# High-risk commands blocked under critical DB load
HIGH_RISK_COMMANDS = frozenset(
    {
        "system_reboot",
        "force_kill_db",
        "drop_connections",
        "shutdown_cluster",
    }
)

# Simulated allowlist for execute_system_command
ALLOWED_COMMANDS = frozenset(
    {
        "restart_service",
        "clear_cache",
        "scale_up",
        "flush_connections",
        "rotate_logs",
        "system_reboot",
        "force_kill_db",
        "drop_connections",
        "shutdown_cluster",
    }
)

# Schema allowlist for NL2SQL
ALLOWED_TABLES = frozenset({"servers", "logs", "incidents"})

SCHEMA_DESCRIPTION = """
Database: system_telemetry.db (SQLite)

Table: servers
  - id (INTEGER PRIMARY KEY)
  - hostname (TEXT)
  - status (TEXT)  -- healthy | degraded | critical
  - cpu_pct (REAL)
  - mem_pct (REAL)
  - disk_pct (REAL)
  - region (TEXT)
  - db_load (REAL)  -- 0-100 database load percentage

Table: logs
  - id (INTEGER PRIMARY KEY)
  - server_id (INTEGER)  -- FK to servers.id
  - timestamp (TEXT)  -- ISO-8601
  - level (TEXT)  -- INFO | WARN | ERROR | CRITICAL
  - message (TEXT)
  - service (TEXT)

Table: incidents
  - id (INTEGER PRIMARY KEY)
  - server_id (INTEGER)  -- FK to servers.id
  - title (TEXT)
  - severity (TEXT)  -- low | medium | high | critical
  - status (TEXT)  -- open | investigating | resolved
  - root_cause (TEXT)
  - created_at (TEXT)  -- ISO-8601
""".strip()


def configure_langsmith() -> None:
    """Enable LangSmith tracing only when an API key is configured."""
    api_key = os.getenv("LANGCHAIN_API_KEY", "").strip()
    has_key = bool(api_key) and not api_key.startswith("your_")

    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "sentinel-v2"))
    os.environ.setdefault(
        "LANGCHAIN_ENDPOINT",
        os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    )

    if has_key:
        # Honor explicit false; otherwise default to enabled when a key exists.
        tracing = os.getenv("LANGCHAIN_TRACING_V2", "true")
        os.environ["LANGCHAIN_TRACING_V2"] = tracing
    else:
        # Avoid noisy 401s when the student has not added a LangSmith key yet.
        os.environ["LANGCHAIN_TRACING_V2"] = "false"


def require_groq_key() -> str:
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("your_"):
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://console.groq.com/keys"
        )
    return GROQ_API_KEY
