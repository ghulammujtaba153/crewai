"""
LangGraph circular self-healing workflow:

Monitor -> Diagnose -> Remediate -> Verify
If Verify fails, set retry=True and return to Diagnose.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langsmith import traceable

from agents.data_intelligence import build_data_intelligence_agent
from agents.diagnostician import build_diagnostician_agent
from agents.monitor import build_monitor_agent
from agents.remediation import build_remediation_agent
from config import MAX_RETRIES, configure_langsmith
from mcp_server.gateway import (
    execute_system_command,
    get_system_logs,
    get_unhealthy_servers,
    query_database,
    query_knowledge_base,
)
from workflow.agent_runner import run_crew_task, summarize

configure_langsmith()


class SentinelState(TypedDict, total=False):
    anomaly: str
    diagnosis: str
    remediation: str
    verification: str
    verified: bool
    retry: bool
    retry_count: int
    messages: Annotated[list[str], operator.add]
    force_verify_fail_once: bool


def _run_agent_task(agent, description: str, expected_output: str) -> str:
    return run_crew_task(agent, description, expected_output)


def monitor_node(state: SentinelState) -> dict[str, Any]:
    # Seed agents with MCP gateway data (agents may still call tools to verify)
    critical_logs = get_system_logs(level="CRITICAL", limit=8)
    error_logs = get_system_logs(level="ERROR", limit=8)
    telemetry = query_database(
        "list hostname, status, cpu_pct, db_load from servers where status is critical or degraded"
    )
    incidents = query_database("list title, severity, status from open incidents")

    agent = build_monitor_agent()
    context = (
        f"CRITICAL LOGS:\n{critical_logs}\n\n"
        f"ERROR LOGS:\n{error_logs}\n\n"
        f"TELEMETRY:\n{telemetry}\n\n"
        f"INCIDENTS:\n{incidents}"
    )
    output = summarize(
        agent.role,
        f"{agent.goal} Produce a structured anomaly report with hosts, symptoms, and severity.",
        context,
    )
    return {
        "anomaly": output,
        "messages": [f"[Monitor] {output}"],
        "retry": False,
        "retry_count": state.get("retry_count", 0),
    }


def diagnose_node(state: SentinelState) -> dict[str, Any]:
    agent = build_diagnostician_agent()
    retry_note = ""
    if state.get("retry"):
        retry_note = (
            f"\n\nRETRY #{state.get('retry_count', 0)}. Prior verification:\n"
            f"{state.get('verification', '')}\n"
            "Refine root-cause and recommend a safer fix."
        )
    kb = query_knowledge_base(state.get("anomaly", "platform outage"))
    logs = get_system_logs(level="ERROR", limit=6)
    context = (
        f"ANOMALY REPORT:\n{state.get('anomaly', '')}\n\n"
        f"KNOWLEDGE BASE (MCP):\n{kb[:2000]}\n\n"
        f"ERROR LOGS (MCP):\n{logs}"
        f"{retry_note}"
    )
    output = summarize(
        agent.role,
        f"{agent.goal} Provide root-cause analysis and recommended remediation actions.",
        context,
    )
    return {
        "diagnosis": output,
        "messages": [f"[Diagnose] {output}"],
        "retry": False,
    }


def remediate_node(state: SentinelState) -> dict[str, Any]:
    agent = build_remediation_agent()
    # Execute remediation through MCP gateway (simulated commands + guardrails)
    cmd_scale = execute_system_command("scale_up", target="platform")
    cmd_cache = execute_system_command("clear_cache", target="cache-tier")
    cmd_reboot = execute_system_command("system_reboot", target="db-primary")
    post_logs = get_system_logs(level="ERROR", limit=4)
    context = (
        f"DIAGNOSIS:\n{state.get('diagnosis', '')}\n\n"
        f"MCP scale_up result:\n{cmd_scale}\n\n"
        f"MCP clear_cache result:\n{cmd_cache}\n\n"
        f"MCP system_reboot attempt (expect guardrail if db_load critical):\n{cmd_reboot}\n\n"
        f"POST-REMEDIATION LOGS:\n{post_logs}"
    )
    output = summarize(
        agent.role,
        f"{agent.goal} Summarize commands attempted, outcomes, and any safety blocks.",
        context,
    )
    return {
        "remediation": output,
        "messages": [f"[Remediate] {output}"],
    }


def verify_node(state: SentinelState) -> dict[str, Any]:
    """
    Verify remediation effectiveness.

    Uses MCP gateway telemetry for a deterministic check, then records the outcome.
    Optionally fails once to exercise the retry loop when force_verify_fail_once is set.
    """
    import json

    logs = get_system_logs(level="CRITICAL", limit=5)
    unhealthy = get_unhealthy_servers()
    unhealthy_count = len(unhealthy)
    telemetry = json.dumps(unhealthy, indent=2)

    retry_count = int(state.get("retry_count", 0))
    force_fail = bool(state.get("force_verify_fail_once", True)) and retry_count == 0

    still_unhealthy = unhealthy_count > 0
    verified = (not force_fail) and (not still_unhealthy)

    if force_fail:
        verification = (
            "VERIFICATION FAILED (initial pass): residual critical signals remain. "
            f"Critical logs snippet:\n{logs[:500]}\nUnhealthy servers:\n{telemetry[:800]}\n"
            "Setting retry flag - returning to Diagnose."
        )
        # Apply a safer follow-up action so the next verify can succeed
        execute_system_command("scale_up", target="api-tier")
        execute_system_command("clear_cache", target="platform")
        return {
            "verification": verification,
            "verified": False,
            "retry": True,
            "retry_count": retry_count + 1,
            "messages": [f"[Verify] {verification}"],
            "force_verify_fail_once": False,
        }

    if still_unhealthy:
        verification = (
            "VERIFICATION FAILED: critical/degraded hosts still present in telemetry.\n"
            f"{telemetry[:800]}"
        )
        return {
            "verification": verification,
            "verified": False,
            "retry": True,
            "retry_count": retry_count + 1,
            "messages": [f"[Verify] {verification}"],
        }

    verification = (
        "VERIFICATION PASSED: no critical/degraded hosts remaining in telemetry. "
        f"Remediation summary was applied. Unhealthy count={unhealthy_count}."
    )
    return {
        "verification": verification,
        "verified": True,
        "retry": False,
        "messages": [f"[Verify] {verification}"],
    }


def route_after_verify(state: SentinelState) -> str:
    if state.get("verified"):
        return "end"
    if int(state.get("retry_count", 0)) < MAX_RETRIES:
        return "diagnose"
    return "end"


def build_sentinel_graph():
    graph = StateGraph(SentinelState)
    graph.add_node("monitor", monitor_node)
    graph.add_node("diagnose", diagnose_node)
    graph.add_node("remediate", remediate_node)
    graph.add_node("verify", verify_node)

    graph.set_entry_point("monitor")
    graph.add_edge("monitor", "diagnose")
    graph.add_edge("diagnose", "remediate")
    graph.add_edge("remediate", "verify")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "diagnose": "diagnose",
            "end": END,
        },
    )
    return graph.compile()


@traceable(name="sentinel_self_heal", run_type="chain")
def run_self_heal(force_verify_fail_once: bool = True) -> SentinelState:
    app = build_sentinel_graph()
    initial: SentinelState = {
        "anomaly": "",
        "diagnosis": "",
        "remediation": "",
        "verification": "",
        "verified": False,
        "retry": False,
        "retry_count": 0,
        "messages": [],
        "force_verify_fail_once": force_verify_fail_once,
    }
    return app.invoke(initial)


@traceable(name="sentinel_nl2sql", run_type="chain")
def run_nl2sql(question: str) -> str:
    agent = build_data_intelligence_agent()
    return _run_agent_task(
        agent,
        description=(
            f"User question: {question}\n\n"
            "Call query_database with this exact natural-language question and present "
            "the tool result clearly. If the tool says the question is out of scope, "
            "explain the limitation gracefully without inventing facts."
        ),
        expected_output="A clear answer based solely on query_database results.",
    )
