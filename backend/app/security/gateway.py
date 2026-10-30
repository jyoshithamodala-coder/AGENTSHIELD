
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


TOOL_REGISTRY = {
    "document_reader": read_document,
    "file_search": search_files,
    "sensitive_data": access_sensitive_data,
    "external_communication": send_external_message
}


TOOL_ARGUMENTS = {
    "document_reader": {"document_id": (str, 64)},
    "file_search": {"keyword": (str, 100)},
    "sensitive_data": {"record_id": (str, 64)},
    "external_communication": {
        "destination": (str, 254),
        "content": (str, 2000)
    }
}


def validate_tool_arguments(tool_name, arguments):
    if not isinstance(arguments, dict):
        return False, "Tool arguments must be an object."

    rules = TOOL_ARGUMENTS.get(tool_name)

    if rules is None:
        return False, "No argument schema exists for this tool."

    required = set(rules.keys())
    supplied = set(arguments.keys())

    missing = required - supplied
    unexpected = supplied - required

    if missing:
        return False, f"Missing required arguments: {sorted(missing)}"

    if unexpected:
        return False, f"Unexpected arguments: {sorted(unexpected)}"

    for field, (expected_type, max_length) in rules.items():
        value = arguments[field]

        if not isinstance(value, expected_type):
            return False, f"Invalid type for argument: {field}"

        if not value.strip():
            return False, f"Argument cannot be empty: {field}"

        if len(value) > max_length:
            return False, f"Argument exceeds length limit: {field}"

    return True, "Arguments validated successfully."


def record_event(request, decision, reason, risk_level):
    initialize_audit_db()

    log_security_event(
        task_id=request.task_id,
        agent_id=request.agent_id,
        tool_name=request.tool_name,
        decision=decision.value if hasattr(decision, "value") else str(decision),
        reason=reason,
        risk_level=risk_level,
        arguments={
            "provided_fields": sorted(request.arguments.keys()),
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


def inspect_retrieved_content(tool_name, result):
    """
    Inspect retrieved document content before releasing it.
    """

    if tool_name == "document_reader" and result.get("success"):
        content = result.get("content", "")
        detection = detect_prompt_injection(content)

        if detection["is_suspicious"]:
            return False, detection["reason"]

    return True, "Retrieved content passed inspection."


def execute_tool(request: ToolRequest):
    """
    Process a new tool request.
    High-impact actions are stored for human approval.
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

    # 1. Reject unknown tools.
    if tool_name not in TOOL_REGISTRY:
        return make_response(
            request,
            SecurityDecision.DENY,
            "Unknown tool. Access denied.",
            "HIGH"
        )

    # 2. Validate arguments.
    is_valid, validation_reason = validate_tool_arguments(
        tool_name,
        request.arguments
    )

    if not is_valid:
        return make_response(
            request,
            SecurityDecision.DENY,
            validation_reason,
            "HIGH"
        )

    # 3. Inspect explicitly supplied untrusted content.
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

    # 4. Evaluate policy without assuming approval.
    policy = evaluate_policy(
        tool_name,
        user_confirmed=False
    )

    decision = policy["decision"]

    # 5. Create approval request if required.
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

    # 6. Stop denied actions.
    if decision != SecurityDecision.ALLOW:
        return make_response(
            request,
            decision,
            policy["reason"],
            policy["risk_level"]
        )

    # 7. Execute authorized low-risk action.
    try:
        result = TOOL_REGISTRY[tool_name](**request.arguments)

        safe, reason = inspect_retrieved_content(tool_name, result)

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


def resolve_approval(approval_id, approved):
    """
    Record a human approval or rejection.
    """

    success, message = resolve_pending_approval(
        approval_id,
        approved
    )

    # Record the approval decision.
    try:
        initialize_audit_db()

        log_security_event(
            task_id="approval_workflow",
            agent_id="human_reviewer",
            tool_name="external_communication",
            decision="ALLOW" if success and approved else "DENY",
            reason=message,
            risk_level="HIGH",
            arguments={"approval_id": approval_id}
        )

    except Exception:
        return False, "Audit logging failed. Approval resolution cannot continue safely."

    return success, message


def execute_approved_tool(approval_id):
    """
    Execute the exact request previously approved by a human.
    """

    try:
        initialize_audit_db()

        # Atomically claim the approved request.
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

        # Approval is currently supported only for external communication.
        if request.tool_name != "external_communication":
            finish_approval(approval_id, success=False)

            return make_response(
                request,
                SecurityDecision.DENY,
                "This approval type is not supported.",
                "HIGH"
            )

        # Revalidate the exact stored request.
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

        # Recheck policy. The approval manager has already
        # confirmed this exact request was approved.
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

        # Execute the simulated communication tool.
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
