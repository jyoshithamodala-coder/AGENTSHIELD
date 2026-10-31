
from app.models.schemas import ToolRequest, SecurityDecision

from app.security.policy import evaluate_policy
from app.security.detector import detect_prompt_injection
from app.security.approval import (
    create_pending_approval,
    resolve_pending_approval,
    consume_approved_action,
    finish_approval
)

from app.audit.logger import (
    initialize_audit_db,
    log_security_event
)

from app.tools.document_reader import read_document
from app.tools.file_search import search_files
from app.tools.sensitive_data import access_sensitive_data
from app.tools.communication import send_external_message
from app.tools.file_manager import file_access_manager
from app.tools.database_manager import database_manager

import json


# --------------------------------------------------
# 1. REGISTERED TOOLS
# --------------------------------------------------

TOOL_REGISTRY = {
    "document_reader": read_document,
    "file_search": search_files,
    "sensitive_data": access_sensitive_data,
    "external_communication": send_external_message,
    "file_access_manager": file_access_manager,
    "database_manager": database_manager
}


# --------------------------------------------------
# 2. OPERATION ARGUMENT RULES
# --------------------------------------------------

SIMPLE_TOOL_ARGUMENTS = {
    "document_reader": {
        "document_id": (str, 64)
    },
    "file_search": {
        "keyword": (str, 100)
    },
    "sensitive_data": {
        "record_id": (str, 64)
    },
    "external_communication": {
        "destination": (str, 254),
        "content": (str, 2000)
    }
}

FILE_OPERATION_ARGUMENTS = {
    "search": {
        "keyword": (str, 100)
    },
    "read": {
        "file_path": (str, 500)
    },
    "create_folder": {
        "folder_name": (str, 500)
    },
    "copy": {
        "source": (str, 500),
        "destination": (str, 500)
    },
    "rename": {
        "source": (str, 500),
        "new_name": (str, 500)
    },
    "edit": {
        "file_path": (str, 500),
        "content": (str, 10000)
    },
    "delete": {
        "file_path": (str, 500)
    }
}

DATABASE_OPERATION_ARGUMENTS = {
    "create_database": {
        "database_name": (str, 63)
    },
    "create_table": {
        "database_name": (str, 63),
        "table": (str, 63),
        "columns": (list, None)
    },
    "list_tables": {
        "database_name": (str, 63)
    },
    "describe_table": {
        "database_name": (str, 63),
        "table": (str, 63)
    },
    "read": {
        "database_name": (str, 63),
        "table": (str, 63)
    },
    "search": {
        "database_name": (str, 63),
        "table": (str, 63),
        "keyword": (str, 500)
    },
    "insert": {
        "database_name": (str, 63),
        "table": (str, 63),
        "record_json": (dict, None)
    },
    "update": {
        "database_name": (str, 63),
        "table": (str, 63),
        "primary_key": (str, 63),
        "record_id": (str, 255),
        "updates_json": (dict, None)
    },
    "delete": {
        "database_name": (str, 63),
        "table": (str, 63),
        "primary_key": (str, 63),
        "record_id": (str, 255)
    }
}

# Operations that may change or remove data.
# They remain blocked until the approval workflow supports them.
FILE_WRITE_OPERATIONS = {
    "create_folder", "copy", "rename", "edit", "delete"
}

DATABASE_WRITE_OPERATIONS = {
    "create_database", "create_table", "insert", "update", "delete"
}


# --------------------------------------------------
# 3. VALIDATION HELPERS
# --------------------------------------------------

def validate_string(value, field, max_length):
    if not isinstance(value, str):
        return False, f"{field} must be a string."

    if not value.strip():
        return False, f"{field} cannot be empty."

    if len(value) > max_length:
        return False, f"{field} exceeds the length limit."

    return True, "Valid."


def validate_columns(columns):
    if not isinstance(columns, list) or not columns:
        return False, "columns must be a non-empty list."

    allowed_types = {
        "INTEGER", "INT", "BIGINT", "SMALLINT",
        "VARCHAR", "TEXT", "DATE", "DATETIME",
        "DECIMAL", "FLOAT", "DOUBLE", "BOOLEAN"
    }

    for column in columns:
        if not isinstance(column, dict):
            return False, "Each column must be an object."

        allowed_fields = {
            "name", "type", "length", "primary_key", "not_null"
        }

        if set(column) - allowed_fields:
            return False, "Unexpected column properties."

        if "name" not in column or "type" not in column:
            return False, "Every column needs a name and type."

        valid, reason = validate_string(
            column["name"], "column name", 63
        )
        if not valid:
            return False, reason

        valid, reason = validate_string(
            column["type"], "column type", 20
        )
        if not valid:
            return False, reason

        if column["type"].upper() not in allowed_types:
            return False, "Unsupported SQL column type."

        if "length" in column:
            if (
                not isinstance(column["length"], int)
                or isinstance(column["length"], bool)
                or not 1 <= column["length"] <= 65535
            ):
                return False, "Invalid column length."

        for flag in ("primary_key", "not_null"):
            if flag in column and not isinstance(column[flag], bool):
                return False, f"{flag} must be true or false."

    return True, "Columns validated."


def validate_tool_arguments(tool_name, arguments):
    if not isinstance(arguments, dict):
        return False, "Tool arguments must be an object."

    # Ordinary fixed-schema tools
    if tool_name in SIMPLE_TOOL_ARGUMENTS:
        rules = SIMPLE_TOOL_ARGUMENTS[tool_name]

        if set(arguments) != set(rules):
            missing = set(rules) - set(arguments)
            unexpected = set(arguments) - set(rules)

            return False, (
                f"Missing arguments: {sorted(missing)}; "
                f"unexpected arguments: {sorted(unexpected)}"
            )

        for field, (expected_type, max_length) in rules.items():
            value = arguments[field]

            if not isinstance(value, expected_type):
                return False, f"Invalid type for {field}."

            if not isinstance(value, str) or not value.strip():
                return False, f"{field} cannot be empty."

            if len(value) > max_length:
                return False, f"{field} exceeds the length limit."

        return True, "Arguments validated successfully."

    # File manager
    if tool_name == "file_access_manager":
        operation = arguments.get("operation")

        if operation not in FILE_OPERATION_ARGUMENTS:
            return False, "Unsupported file operation."

        rules = FILE_OPERATION_ARGUMENTS[operation]
        expected_fields = {"operation"} | set(rules)

        if set(arguments) != expected_fields:
            missing = expected_fields - set(arguments)
            unexpected = set(arguments) - expected_fields

            return False, (
                f"Missing arguments: {sorted(missing)}; "
                f"unexpected arguments: {sorted(unexpected)}"
            )

        for field, (expected_type, max_length) in rules.items():
            value = arguments[field]

            if not isinstance(value, expected_type):
                return False, f"Invalid type for {field}."

            if expected_type is str:
                valid, reason = validate_string(
                    value, field, max_length
                )
                if not valid:
                    return False, reason

        return True, "File arguments validated successfully."

    # Database manager
    if tool_name == "database_manager":
        operation = arguments.get("operation")

        if operation not in DATABASE_OPERATION_ARGUMENTS:
            return False, "Unsupported database operation."

        rules = DATABASE_OPERATION_ARGUMENTS[operation]

        # record_id and primary_key are optional for read.
        required_fields = {"operation"} | set(rules)

        if operation == "read":
            allowed_fields = required_fields | {
                "record_id", "primary_key"
            }

            if not set(arguments).issubset(allowed_fields):
                return False, "Unexpected database arguments."

            if "record_id" in arguments and "primary_key" not in arguments:
                return False, "primary_key is required when record_id is supplied."

            if "primary_key" in arguments and "record_id" not in arguments:
                return False, "record_id is required when primary_key is supplied."

        elif set(arguments) != required_fields:
            missing = required_fields - set(arguments)
            unexpected = set(arguments) - required_fields

            return False, (
                f"Missing arguments: {sorted(missing)}; "
                f"unexpected arguments: {sorted(unexpected)}"
            )

        for field, (expected_type, max_length) in rules.items():
            value = arguments[field]

            if not isinstance(value, expected_type):
                return False, f"Invalid type for {field}."

            if expected_type is str:
                valid, reason = validate_string(
                    value, field, max_length
                )
                if not valid:
                    return False, reason

        if operation == "read" and "record_id" in arguments:
            valid, reason = validate_string(
                str(arguments["record_id"]), "record_id", 255
            )
            if not valid:
                return False, reason

        if operation == "create_table":
            valid, reason = validate_columns(arguments["columns"])
            if not valid:
                return False, reason

        return True, "Database arguments validated successfully."

    return False, "No argument schema exists for this tool."


# --------------------------------------------------
# 4. OPERATION RISK CHECK
# --------------------------------------------------

def is_write_operation(request):
    arguments = request.arguments
    operation = arguments.get("operation")

    if request.tool_name == "file_access_manager":
        return operation in FILE_WRITE_OPERATIONS

    if request.tool_name == "database_manager":
        return operation in DATABASE_WRITE_OPERATIONS

    return False


# --------------------------------------------------
# 5. AUDIT LOGGING
# --------------------------------------------------

def record_event(request, decision, reason, risk_level):
    initialize_audit_db()

    log_security_event(
        task_id=request.task_id,
        agent_id=request.agent_id,
        tool_name=request.tool_name,
        decision=(
            decision.value
            if hasattr(decision, "value")
            else str(decision)
        ),
        reason=reason,
        risk_level=risk_level,
        arguments={
            "provided_fields": sorted(request.arguments.keys()),
            "operation": request.arguments.get("operation"),
            "source": request.source
        }
    )


def make_response(
    request,
    decision,
    reason,
    risk_level,
    executed=False,
    result=None,
    approval_id=None
):
    record_event(request, decision, reason, risk_level)

    return {
        "decision": decision,
        "reason": reason,
        "executed": executed,
        "result": result,
        "risk_level": risk_level,
        "approval_id": approval_id
    }


# --------------------------------------------------
# 6. INSPECT RETRIEVED CONTENT
# --------------------------------------------------

def inspect_retrieved_content(tool_name, result):
    """
    Inspect retrieved document content before releasing it.
    """

    if not isinstance(result, dict):
        return True, "Tool returned a non-dictionary result."

    if tool_name == "document_reader" and result.get("success"):
        content = result.get("content", "")

        detection = detect_prompt_injection(content)

        if detection["is_suspicious"]:
            return False, detection["reason"]

    return True, "Retrieved content passed inspection."


# --------------------------------------------------
# 7. MAIN SECURITY GATEWAY
# --------------------------------------------------

def execute_tool(request: ToolRequest):
    """
    Validate, authorize, execute, and audit a tool request.
    """

    try:
        initialize_audit_db()
    except Exception:
        return {
            "decision": SecurityDecision.DENY,
            "reason": "Security audit system unavailable. Request blocked.",
            "executed": False,
            "risk_level": "HIGH",
            "approval_id": None
        }

    tool_name = request.tool_name

    # Step 1: Reject unknown tools.
    if tool_name not in TOOL_REGISTRY:
        return make_response(
            request,
            SecurityDecision.DENY,
            "Unknown tool. Access denied.",
            "HIGH"
        )

    # Step 2: Validate arguments.
    valid, validation_reason = validate_tool_arguments(
        tool_name,
        request.arguments
    )

    if not valid:
        return make_response(
            request,
            SecurityDecision.DENY,
            validation_reason,
            "HIGH"
        )

    # Step 3: Inspect untrusted supplied content.
    if request.source == "untrusted_document":
        content = request.arguments.get("content", "")
        detection = detect_prompt_injection(content)

        if detection["is_suspicious"]:
            return make_response(
                request,
                SecurityDecision.DENY,
                detection["reason"],
                "HIGH"
            )

    # Step 4: Block file/database writes until their approval
    # workflow is implemented and tested.
    if is_write_operation(request):
        return make_response(
            request,
            SecurityDecision.DENY,
            "This file/database write operation is not enabled yet. "
            "Human approval support must be implemented first.",
            "HIGH"
        )

    # Step 5: Ask the existing policy engine.
    policy = evaluate_policy(
        tool_name,
        user_confirmed=False
    )

    decision = policy["decision"]

    # Step 6: Create approval for tools already supported
    # by the existing approval workflow.
    if decision == SecurityDecision.REQUIRE_APPROVAL:
        try:
            approval_id = create_pending_approval(request)

            return make_response(
                request,
                SecurityDecision.REQUIRE_APPROVAL,
                policy["reason"],
                policy["risk_level"],
                approval_id=approval_id
            )

        except Exception:
            return make_response(
                request,
                SecurityDecision.DENY,
                "Could not create approval request. Action blocked.",
                "HIGH"
            )

    # Step 7: Stop denied or unsupported actions.
    if decision != SecurityDecision.ALLOW:
        return make_response(
            request,
            decision,
            policy["reason"],
            policy["risk_level"]
        )

    # Step 8: Execute only through the trusted registry.
    try:
        result = TOOL_REGISTRY[tool_name](**request.arguments)

        safe, reason = inspect_retrieved_content(
            tool_name,
            result
        )

        if not safe:
            return make_response(
                request,
                SecurityDecision.DENY,
                "Retrieved document blocked: " + reason,
                "HIGH",
                executed=True
            )

        return make_response(
            request,
            SecurityDecision.ALLOW,
            policy["reason"],
            policy["risk_level"],
            executed=True,
            result=result
        )

    except Exception:
        return make_response(
            request,
            SecurityDecision.DENY,
            "Tool execution failed safely.",
            "HIGH"
        )


# --------------------------------------------------
# 8. RESOLVE HUMAN APPROVAL
# --------------------------------------------------

def resolve_approval(approval_id, approved):
    success, message = resolve_pending_approval(
        approval_id,
        approved
    )

    try:
        initialize_audit_db()

        log_security_event(
            task_id="approval_workflow",
            agent_id="human_reviewer",
            tool_name="approval_workflow",
            decision="ALLOW" if success and approved else "DENY",
            reason=message,
            risk_level="HIGH",
            arguments={"approval_id": approval_id}
        )

    except Exception:
        return False, (
            "Audit logging failed. Approval resolution "
            "cannot continue safely."
        )

    return success, message


# --------------------------------------------------
# 9. EXECUTE APPROVED ACTION
# --------------------------------------------------

def execute_approved_tool(approval_id):
    """
    The current approval executor supports only
    external communication. Other approved tool types
    must not be executed until their workflow is added.
    """

    try:
        initialize_audit_db()

        stored_request = consume_approved_action(approval_id)

        if stored_request is None:
            return {
                "decision": SecurityDecision.DENY,
                "reason": "Invalid, expired, or already-used approval.",
                "executed": False,
                "risk_level": "HIGH",
                "approval_id": None
            }

        request = ToolRequest.model_validate(stored_request)

        # Preserve the existing approval scope.
        if request.tool_name != "external_communication":
            finish_approval(approval_id, success=False)

            return make_response(
                request,
                SecurityDecision.DENY,
                "This approval type is not supported.",
                "HIGH"
            )

        valid, reason = validate_tool_arguments(
            request.tool_name,
            request.arguments
        )

        if not valid:
            finish_approval(approval_id, success=False)

            return make_response(
                request,
                SecurityDecision.DENY,
                reason,
                "HIGH"
            )

        policy = evaluate_policy(
            request.tool_name,
            user_confirmed=True
        )

        if policy["decision"] != SecurityDecision.ALLOW:
            finish_approval(approval_id, success=False)

            return make_response(
                request,
                SecurityDecision.DENY,
                "Policy rejected the approved action.",
                "HIGH"
            )

        result = TOOL_REGISTRY[request.tool_name](
            **request.arguments
        )

        finish_approval(approval_id, success=True)

        return make_response(
            request,
            SecurityDecision.ALLOW,
            "Human-approved action executed successfully.",
            "HIGH",
            executed=True,
            result=result
        )

    except Exception:
        try:
            finish_approval(approval_id, success=False)
        except Exception:
            pass

        return {
            "decision": SecurityDecision.DENY,
            "reason": "Approved action failed safely.",
            "executed": False,
            "risk_level": "HIGH",
            "approval_id": None
        }
