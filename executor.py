# executor.py

from database import get_db
from security.validators import safe_calculate


def execute_operation(user, operation, arguments):
    """
    Execute a predefined operation.

    This function must only be called after the Security Engine returns
    ALLOW. It still applies ownership checks to database operations.
    """

    if operation == "calculator":
        result = safe_calculate(arguments["expression"])

        return {
            "message": f"Result: {result}",
            "value": result,
        }

    if operation == "save_note":
        with get_db() as db:
            cursor = db.execute(
                """
                INSERT INTO notes(user_id, title, content)
                VALUES (?, ?, ?)
                """,
                (
                    user["id"],
                    arguments["title"],
                    arguments["content"],
                ),
            )

            note_id = cursor.lastrowid

        return {
            "message": f"Note saved successfully. ID: {note_id}",
            "note_id": note_id,
        }

    if operation == "list_notes":
        with get_db() as db:
            rows = db.execute(
                """
                SELECT id, title, created_at
                FROM notes
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 50
                """,
                (user["id"],),
            ).fetchall()

        notes = [dict(row) for row in rows]

        return {
            "message": (
                f"Found {len(notes)} note(s)."
                if notes
                else "You have no saved notes."
            ),
            "notes": notes,
        }

    if operation == "read_note":
        with get_db() as db:
            row = db.execute(
                """
                SELECT id, title, content, created_at
                FROM notes
                WHERE id = ? AND user_id = ?
                """,
                (arguments["note_id"], user["id"]),
            ).fetchone()

        if row is None:
            return {"message": "Note not found in your account."}

        note = dict(row)

        return {
            "message": f'{note["title"]}: {note["content"]}',
            "note": note,
        }

    # Destructive operations intentionally have no executor here.
    # Unknown operations also fail closed.
    raise PermissionError("Operation is not executable.")