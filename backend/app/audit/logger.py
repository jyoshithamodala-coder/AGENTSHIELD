
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "agentshield.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_audit_db():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            task_id TEXT,
            agent_id TEXT,
            tool_name TEXT,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            risk_level TEXT,
            arguments TEXT
        )
    """)

    connection.commit()
    connection.close()


def log_security_event(
    task_id,
    agent_id,
    tool_name,
    decision,
    reason,
    risk_level="UNKNOWN",
    arguments=None
):
    connection = get_connection()

    connection.execute("""
        INSERT INTO audit_logs (
            timestamp,
            task_id,
            agent_id,
            tool_name,
            decision,
            reason,
            risk_level,
            arguments
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        task_id,
        agent_id,
        tool_name,
        decision,
        reason,
        risk_level,
        json.dumps(arguments or {})
    ))

    connection.commit()
    connection.close()


def get_audit_logs(limit=100):
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    rows = connection.execute("""
        SELECT * FROM audit_logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    connection.close()

    return [dict(row) for row in rows]
