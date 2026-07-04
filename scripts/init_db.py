"""Create and seed system_telemetry.db with servers, logs, and incidents."""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import DATA_DIR, DB_PATH  # noqa: E402


def init_db(db_path: Path | None = None) -> Path:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE servers (
            id INTEGER PRIMARY KEY,
            hostname TEXT NOT NULL,
            status TEXT NOT NULL,
            cpu_pct REAL NOT NULL,
            mem_pct REAL NOT NULL,
            disk_pct REAL NOT NULL,
            region TEXT NOT NULL,
            db_load REAL NOT NULL
        );

        CREATE TABLE logs (
            id INTEGER PRIMARY KEY,
            server_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            service TEXT NOT NULL,
            FOREIGN KEY (server_id) REFERENCES servers(id)
        );

        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY,
            server_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            root_cause TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (server_id) REFERENCES servers(id)
        );
        """
    )

    servers = [
        (1, "web-01.us-east", "healthy", 32.1, 48.0, 55.0, "us-east", 22.0),
        (2, "web-02.us-east", "degraded", 91.4, 72.0, 60.0, "us-east", 35.0),
        (3, "api-01.us-west", "critical", 97.8, 88.5, 71.0, "us-west", 42.0),
        (4, "db-primary.us-east", "degraded", 78.0, 85.2, 68.0, "us-east", 92.0),
        (5, "db-replica.us-east", "healthy", 41.0, 55.0, 50.0, "us-east", 48.0),
        (6, "cache-01.us-west", "healthy", 28.0, 40.0, 35.0, "us-west", 10.0),
        (7, "worker-01.us-east", "critical", 95.0, 93.0, 80.0, "us-east", 55.0),
        (8, "worker-02.us-east", "healthy", 22.0, 30.0, 40.0, "us-east", 12.0),
    ]
    cur.executemany(
        "INSERT INTO servers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        servers,
    )

    now = datetime.now(timezone.utc)
    log_rows = [
        (1, 2, (now - timedelta(minutes=12)).isoformat(), "WARN",
         "CPU utilization sustained above 90% for 5 minutes", "nginx"),
        (2, 2, (now - timedelta(minutes=10)).isoformat(), "ERROR",
         "Upstream timeout connecting to api-01.us-west", "nginx"),
        (3, 3, (now - timedelta(minutes=8)).isoformat(), "CRITICAL",
         "Request queue depth exceeded threshold (512)", "api-gateway"),
        (4, 3, (now - timedelta(minutes=7)).isoformat(), "ERROR",
         "Connection pool exhausted: no free connections", "api-gateway"),
        (5, 4, (now - timedelta(minutes=6)).isoformat(), "ERROR",
         "Slow query log: SELECT on orders took 12.4s", "postgres"),
        (6, 4, (now - timedelta(minutes=5)).isoformat(), "CRITICAL",
         "Database load critical: active connections at 92%", "postgres"),
        (7, 4, (now - timedelta(minutes=4)).isoformat(), "WARN",
         "Replication lag increased to 45 seconds", "postgres"),
        (8, 7, (now - timedelta(minutes=3)).isoformat(), "CRITICAL",
         "OutOfMemoryError in job processor heap", "worker"),
        (9, 7, (now - timedelta(minutes=2)).isoformat(), "ERROR",
         "Job backlog growing: 14000 pending tasks", "worker"),
        (10, 1, (now - timedelta(minutes=15)).isoformat(), "INFO",
         "Health check passed", "nginx"),
        (11, 5, (now - timedelta(minutes=9)).isoformat(), "INFO",
         "Replica catch-up completed", "postgres"),
        (12, 6, (now - timedelta(minutes=1)).isoformat(), "INFO",
         "Cache hit ratio 0.94", "redis"),
    ]
    cur.executemany(
        "INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)",
        log_rows,
    )

    incidents = [
        (1, 3, "API gateway connection pool exhaustion", "critical", "open",
         None, (now - timedelta(minutes=8)).isoformat()),
        (2, 4, "Primary database under critical load", "critical", "investigating",
         "Long-running queries and connection spike", (now - timedelta(minutes=6)).isoformat()),
        (3, 7, "Worker OOM and job backlog", "high", "open",
         None, (now - timedelta(minutes=3)).isoformat()),
        (4, 2, "Elevated CPU on web-02", "medium", "open",
         None, (now - timedelta(minutes=12)).isoformat()),
        (5, 1, "Routine maintenance window", "low", "resolved",
         "Planned patching", (now - timedelta(days=2)).isoformat()),
    ]
    cur.executemany(
        "INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?)",
        incidents,
    )

    conn.commit()
    conn.close()
    print(f"Initialized database at {path}")
    return path


if __name__ == "__main__":
    init_db()
