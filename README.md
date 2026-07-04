# Sentinel v2.0 — Autonomous System Health Guardian

Intelligent multi-agent monitoring for a cloud-native platform. Sentinel detects anomalies, diagnoses root causes via RAG, proposes safe remediation, and answers natural-language questions over operational telemetry (NL2SQL).

## Architecture

| Layer | Technology |
|-------|------------|
| Agents | CrewAI (Monitor, Diagnostician, Remediation, Data Intelligence) |
| Workflow | LangGraph circular self-healing loop |
| Gateway | MCP server (sole entry point for system interaction) |
| LLM | Groq (`llama-3.3-70b-versatile`) |
| Observability | LangSmith |

**Self-healing loop:** `Monitor → Diagnose → Remediate → Verify`  
If verification fails, a `retry` flag is set and control returns to **Diagnose**.

Agents interact with the platform **only** through MCP tools:

- `get_system_logs()`
- `execute_system_command()` (simulated / read-only)
- `query_knowledge_base()`
- `query_database(nl_query)` (NL2SQL)

## Setup (separate environment)

```powershell
cd "d:\AiML Projects\crewAI"
# Requires Python 3.10–3.13 (CrewAI does not support 3.14 yet)
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set:

1. **`GROQ_API_KEY`** — free key from [console.groq.com/keys](https://console.groq.com/keys)
2. **`LANGCHAIN_API_KEY`** — free key from [smith.langchain.com](https://smith.langchain.com) (see below)

Initialize the telemetry database:

```powershell
python main.py init-db
```

## LangSmith setup (assignment screenshot)

1. Create a free account at [https://smith.langchain.com](https://smith.langchain.com)
2. Open **Settings → API Keys** and create a key
3. Put it in `.env` as `LANGCHAIN_API_KEY=...`
4. Ensure:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sentinel-v2
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

5. Run an NL2SQL query:

```powershell
python main.py nl2sql "Which servers have CPU above 90?"
```

6. Open project **sentinel-v2** in LangSmith, open the run, and screenshot the span where natural language is translated to SQL.

## Usage

```powershell
# Self-healing loop (Monitor → Diagnose → Remediate → Verify, with retry)
python main.py heal

# Natural language → SQL (Data Intelligence Agent)
python main.py nl2sql "Which servers have CPU above 90?"
python main.py nl2sql "List open critical incidents"
python main.py nl2sql "What is the CEO's favorite color?"   # graceful degradation

# Re-seed database
python main.py init-db

# Run MCP server standalone (stdio)
python -m mcp_server.server
```

## Safety guardrails

The Remediation path blocks **high-risk** commands (`system_reboot`, `force_kill_db`, etc.) when any server reports `db_load >= 80`. Safer alternatives (`clear_cache`, `scale_up`) remain allowed.

## Project layout

```
crewAI/
├── main.py
├── config.py
├── agents/           # Four CrewAI agents
├── workflow/         # LangGraph circular loop
├── mcp_server/       # MCP gateway + tool implementations
├── tools/            # CrewAI tools wrapping MCP
├── data/             # system_telemetry.db + knowledge_base
└── scripts/          # init_db.py
```

## Requirements coverage

| Requirement | Implementation |
|-------------|----------------|
| A. Four specialized agents | `agents/` |
| B. DB + NL2SQL + graceful degradation | `data/system_telemetry.db`, `query_database` |
| C. LangGraph circular loop + retry | `workflow/graph.py` |
| D. MCP-only gateway (4 tools) | `mcp_server/` |
| E. Safety guardrails + LangSmith | remediation checks + tracing env |
