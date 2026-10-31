# database.py

import os
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash


DB_PATH = Path(
    os.getenv(
        "AEGIS_DB_PATH",
        str(Path(__file__).resolve().parent / "aegis.db"),
    )
)


def get_db():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'admin'))
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                operation TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
                    ON DELETE SET NULL
            );
        """)

        # Create demo users only when the database is empty.
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            admin_password = os.getenv(
                "AEGIS_ADMIN_PASSWORD",
                "ChangeMe_Admin_123!",
            )
            user_password = os.getenv(
                "AEGIS_USER_PASSWORD",
                "ChangeMe_User_123!",
            )

            db.execute(
                """
                INSERT INTO users(username, password_hash, role)
                VALUES (?, ?, ?)
                """,
                (
                    "admin",
                    generate_password_hash(admin_password),
                    "admin",
                ),
            )

            db.execute(
                """
                INSERT INTO users(username, password_hash, role)
                VALUES (?, ?, ?)
                """,
                (
                    "user",
                    generate_password_hash(user_password),
                    "user",
                ),
            )


def log_event(user_id, operation, decision, reason):
    """Record a security event without storing credentials or API keys."""

    with get_db() as db:
        db.execute(
            """
            INSERT INTO audit_logs(user_id, operation, decision, reason)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                str(operation)[:80],
                str(decision)[:20],
                str(reason)[:500],
            ),
        )