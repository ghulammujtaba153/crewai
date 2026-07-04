#!/usr/bin/env python3
"""Sentinel v2.0 - Autonomous System Health Guardian CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import configure_langsmith  # noqa: E402

configure_langsmith()


def cmd_init_db(_: argparse.Namespace) -> int:
    from scripts.init_db import init_db

    init_db()
    return 0


def cmd_heal(args: argparse.Namespace) -> int:
    from workflow.graph import run_self_heal

    print("=" * 60)
    print("Sentinel v2.0 - Self-Healing Loop")
    print("Monitor -> Diagnose -> Remediate -> Verify (retry on failure)")
    print("=" * 60)

    # Re-seed so each heal run starts from known anomalies
    from scripts.init_db import init_db

    init_db()

    result = run_self_heal(force_verify_fail_once=not args.no_forced_retry)
    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    print(f"verified:     {result.get('verified')}")
    print(f"retry_count:  {result.get('retry_count')}")
    print(f"\n--- Anomaly ---\n{result.get('anomaly', '')[:1200]}")
    print(f"\n--- Diagnosis ---\n{result.get('diagnosis', '')[:1200]}")
    print(f"\n--- Remediation ---\n{result.get('remediation', '')[:1200]}")
    print(f"\n--- Verification ---\n{result.get('verification', '')[:1200]}")
    return 0 if result.get("verified") else 1


def cmd_nl2sql(args: argparse.Namespace) -> int:
    from workflow.graph import run_nl2sql

    question = " ".join(args.question).strip()
    if not question:
        print("Provide a question, e.g. python main.py nl2sql \"Which servers have CPU above 90?\"")
        return 2

    print("=" * 60)
    print("Sentinel v2.0 - Data Intelligence (NL2SQL)")
    print("=" * 60)
    print(f"Question: {question}\n")

    # Direct MCP path is also traced (useful if agent overhead fails)
    if args.direct:
        from mcp_server.gateway import query_database

        answer = query_database(question)
    else:
        answer = run_nl2sql(question)

    print(answer)
    print(
        "\nTip: Open LangSmith project 'sentinel-v2' and screenshot the NL2SQL trace."
    )
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    from mcp_server.server import main as mcp_main

    mcp_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sentinel v2.0 - Autonomous System Health Guardian",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Create/seed system_telemetry.db")
    p_init.set_defaults(func=cmd_init_db)

    p_heal = sub.add_parser("heal", help="Run Monitor->Diagnose->Remediate->Verify loop")
    p_heal.add_argument(
        "--no-forced-retry",
        action="store_true",
        help="Do not force the first verification to fail (retry demo off)",
    )
    p_heal.set_defaults(func=cmd_heal)

    p_nl = sub.add_parser("nl2sql", help="Ask a natural-language telemetry question")
    p_nl.add_argument("question", nargs="+", help="Natural language question")
    p_nl.add_argument(
        "--direct",
        action="store_true",
        help="Call MCP query_database directly (still LangSmith-traced)",
    )
    p_nl.set_defaults(func=cmd_nl2sql)

    p_mcp = sub.add_parser("mcp", help="Run MCP server on stdio")
    p_mcp.set_defaults(func=cmd_mcp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
