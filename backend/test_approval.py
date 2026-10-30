
from app.models.schemas import ToolRequest
from app.security.approval import (
    create_pending_approval,
    resolve_pending_approval,
    consume_approved_action,
    finish_approval
)


# Create a simulated external communication request.
request = ToolRequest(
    agent_id="agent_001",
    tool_name="external_communication",
    arguments={
        "destination": "demo@example.test",
        "content": "AgentShield approval test."
    },
    source="user_request",
    task_id="approval_test_001"
)

# 1. Create approval request.
approval_id = create_pending_approval(request)

print("Approval ID created:", approval_id)

# 2. Approve the request.
success, message = resolve_pending_approval(
    approval_id,
    approved=True
)

print("Approval result:", success, message)

# 3. Consume the approved action.
approved_request = consume_approved_action(approval_id)

assert approved_request is not None
assert approved_request["tool_name"] == "external_communication"
assert approved_request["arguments"]["destination"] == "demo@example.test"

print("Exact approved request retrieved successfully.")

# 4. Mark it as executed.
finish_approval(approval_id, success=True)

# 5. Verify it cannot be consumed again.
second_attempt = consume_approved_action(approval_id)

assert second_attempt is None

print("One-time approval test passed!")
