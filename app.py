# app.py — beginning of file

import os
from dotenv import load_dotenv

# Load environment variables before importing modules that use them.
load_dotenv()

from functools import wraps
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from agent import plan_request
from database import get_db, init_db, log_event
from executor import execute_operation
from security.engine import evaluate_operation
from security.policies import MAX_MESSAGE_LENGTH



app = Flask(__name__)

secret_key = os.getenv("FLASK_SECRET_KEY", "")

if not secret_key or secret_key.startswith("replace_with_"):
    raise RuntimeError(
        "Set a strong FLASK_SECRET_KEY in your .env file before starting."
    )

app.secret_key = secret_key
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # Local development only; use HTTPS in production.
    MAX_CONTENT_LENGTH=16 * 1024,
)

init_db()


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    with get_db() as db:
        row = db.execute(
            "SELECT id, username, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    return dict(row) if row else None


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify({"error": "Please log in first."}), 401

        return function(*args, **kwargs)

    return wrapper


@app.get("/")
def index():
    user = current_user()

    if user is None:
        return redirect(url_for("login_page"))

    return render_template("index.html", user=user)


@app.get("/login")
def login_page():
    if current_user():
        return redirect(url_for("index"))

    return render_template("login.html")


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request."}), 400

    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Invalid username or password."}), 400

    username = username.strip()

    if not username or len(username) > 80 or len(password) > 1024:
        return jsonify({"error": "Invalid username or password."}), 400

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None or not check_password_hash(
        row["password_hash"], password
    ):
        log_event(None, "LOGIN", "DENY", "Invalid credentials")
        return jsonify({"error": "Invalid username or password."}), 401

    session.clear()
    session["user_id"] = row["id"]

    log_event(row["id"], "LOGIN", "ALLOW", "Successful login")

    return jsonify({"ok": True, "redirect": "/"})


@app.post("/api/logout")
@login_required
def api_logout():
    user = current_user()

    log_event(user["id"], "LOGOUT", "ALLOW", "User logged out")

    session.clear()

    return jsonify({"ok": True})


@app.post("/api/chat")
@login_required
def api_chat():
    user = current_user()

    if user is None:
        return jsonify({"error": "Please log in again."}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request body."}), 400

    message = data.get("message")

    if not isinstance(message, str):
        return jsonify({"error": "Message must be text."}), 400

    message = message.strip()

    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "error": f"Message exceeds {MAX_MESSAGE_LENGTH} characters."
        }), 400

    # Stage 1: Ask Gemini to propose a response or operation.
    try:
        proposal = plan_request(message)
    except Exception:
        # Do not send API keys, provider errors or stack traces to the browser.
        log_event(
            user["id"],
            "GEMINI_PLANNING",
            "ERROR",
            "Planning failed; details withheld from client",
        )

        return jsonify({
            "reply": (
                "Gemini could not process this request. "
                "Check the server configuration and logs."
            ),
            "decision": "ERROR",
        }), 502

    # Stage 2: Ordinary answer; no tool is executed.
    if proposal["kind"] == "answer":
        log_event(
            user["id"],
            "CHAT_ANSWER",
            "ALLOW",
            "No operation requested",
        )

        return jsonify({
            "reply": proposal["message"],
            "decision": "NO_OPERATION",
        })

    operation = proposal["operation"]
    arguments = proposal["arguments"]

    # Stage 3: Every proposed operation must pass the Security Engine.
    verdict = evaluate_operation(user, operation, arguments)

    if verdict["decision"] != "ALLOW":
        log_event(
            user["id"],
            operation,
            "DENY",
            verdict["reason"],
        )

        return jsonify({
            "reply": "The Security Engine blocked this operation.",
            "decision": "DENY",
            "reason": verdict["reason"],
        })

    # Stage 4: Execute only the validated arguments returned by the engine.
    try:
        result = execute_operation(
            user,
            operation,
            verdict["validated_arguments"],
        )

        log_event(
            user["id"],
            operation,
            "ALLOW",
            "Operation passed security checks and executed",
        )

        return jsonify({
            "reply": result.get("message", "Operation completed."),
            "decision": "ALLOW",
            "operation": operation,
            "result": result,
        })

    except Exception:
        log_event(
            user["id"],
            operation,
            "ERROR",
            "Execution failed; details withheld from client",
        )

        return jsonify({
            "reply": "The approved operation failed during execution.",
            "decision": "ERROR",
        }), 500


@app.get("/api/audit")
@login_required
def api_audit():
    user = current_user()

    with get_db() as db:
        if user["role"] == "admin":
            rows = db.execute(
                """
                SELECT a.id, u.username, a.operation, a.decision,
                       a.reason, a.created_at
                FROM audit_logs a
                LEFT JOIN users u ON u.id = a.user_id
                ORDER BY a.id DESC
                LIMIT 100
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT a.id, u.username, a.operation, a.decision,
                       a.reason, a.created_at
                FROM audit_logs a
                LEFT JOIN users u ON u.id = a.user_id
                WHERE a.user_id = ?
                ORDER BY a.id DESC
                LIMIT 50
                """,
                (user["id"],),
            ).fetchall()

    return jsonify({"logs": [dict(row) for row in rows]})


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )