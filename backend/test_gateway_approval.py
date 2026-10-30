
from app.models.schemas import ToolRequest, SecurityDecision
from app.security.gateway import (
    execute_tool,
    resolve_approval,
    execute_approved_tool
)


# 1. Submit a new external communication request.
request = ToolRequest(
    agent_id="agent_001",
    tool_name="external_communication",
    arguments={
        "destination": "demo@example.test",
        "content": "AgentShield approval integration test."
    },
    source="user_request",
    task_id="gateway_approval_001"
)

response = execute_tool(request)

print("\nSTEP 1: Initial gateway response")
print(response)

assert response["decision"] == SecurityDecision.REQUIRE_APPROVAL
assert response["executed"] is False
assert response["approval_id"] is not None

approval_id = response["approval_id"]


# 2. Simulate a human approving the exact pending action.
success, message = resolve_approval(
    approval_id,
    approved=True
)

print("\nSTEP 2: Human approval")
print(success, message)

assert success is True


# 3. Execute the approved action.
execution = execute_approved_tool(approval_id)

print("\nSTEP 3: Approved execution")
print(execution)

assert execution["decision"] == SecurityDecision.ALLOW
assert execution["executed"] is True
assert execution["result"]["simulated"] is True


# 4. Verify that the same approval cannot be reused.
second_attempt = execute_approved_tool(approval_id)

print("\nSTEP 4: Replay attempt")
print(second_attempt)

assert second_attempt["decision"] == SecurityDecision.DENY
assert second_attempt["executed"] is False

print("\nSUCCESS: Gateway approval integration passed!")
