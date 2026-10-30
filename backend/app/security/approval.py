
import json
import secrets
import sqlite3
import time

from app.audit.logger import DB_PATH


APPROVAL_EXPIRY_SECONDS = 300


def get_approval_connection():
    return sqlite3.connect(DB_PATH, timeout=10)


def initialize_approval_db():
    connection = get_approval_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS pending_approvals (
            approval_id TEXT PRIMARY KEY,
            request_data TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            status TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def create_pending_approval(request):
    """
    Store the exact tool request and generate an unpredictable ID.
    """

    initialize_approval_db()

    approval_id = secrets.token_urlsafe(32)
    current_time = time.time()

    request_data = request.model_dump(mode="json")

    connection = get_approval_connection()

    connection.execute("""
        INSERT INTO pending_approvals (
            approval_id,
            request_data,
            created_at,
            expires_at,
            status
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        approval_id,
        json.dumps(request_data, sort_keys=True),
        current_time,
        current_time + APPROVAL_EXPIRY_SECONDS,
        "PENDING"
    ))

    connection.commit()
    connection.close()

    return approval_id


def resolve_pending_approval(approval_id, approved):
    """
    Approve or reject a pending action.
    A pending action can only be resolved once.
    """

    connection = get_approval_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT expires_at, status
            FROM pending_approvals
            WHERE approval_id = ?
        """, (approval_id,)).fetchone()

        if row is None:
            connection.rollback()
            return False, "Approval request not found."

        expires_at, status = row

        if status != "PENDING":
            connection.rollback()
            return False, "Approval request has already been resolved."

        if time.time() >= expires_at:
            connection.execute("""
                UPDATE pending_approvals
                SET status = 'EXPIRED'
                WHERE approval_id = ? AND status = 'PENDING'
            """, (approval_id,))

            connection.commit()
            return False, "Approval request has expired."

        new_status = "APPROVED" if approved else "REJECTED"

        connection.execute("""
            UPDATE pending_approvals
            SET status = ?
            WHERE approval_id = ? AND status = 'PENDING'
        """, (new_status, approval_id))

        connection.commit()

        return True, f"Action {new_status.lower()} successfully."

    finally:
        connection.close()


def consume_approved_action(approval_id):
    """
    Atomically claim an approved action for one-time execution.
    """

    connection = get_approval_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT request_data, expires_at
            FROM pending_approvals
            WHERE approval_id = ? AND status = 'APPROVED'
        """, (approval_id,)).fetchone()

        if row is None:
            connection.rollback()
            return None

        request_data, expires_at = row

        if time.time() >= expires_at:
            connection.execute("""
                UPDATE pending_approvals
                SET status = 'EXPIRED'
                WHERE approval_id = ? AND status = 'APPROVED'
            """, (approval_id,))

            connection.commit()
            return None

        connection.execute("""
            UPDATE pending_approvals
            SET status = 'EXECUTING'
            WHERE approval_id = ? AND status = 'APPROVED'
        """, (approval_id,))

        connection.commit()

        return json.loads(request_data)

    finally:
        connection.close()


def finish_approval(approval_id, success):
    """
    Mark a claimed action as executed or failed.
    """

    connection = get_approval_connection()

    connection.execute("""
        UPDATE pending_approvals
        SET status = ?
        WHERE approval_id = ? AND status = 'EXECUTING'
    """, (
        "EXECUTED" if success else "FAILED",
        approval_id
    ))

    connection.commit()
    connection.close()
