
from app.models.schemas import ToolRequest
from app.security.gateway import execute_tool


# Test 1: Valid document request
valid_request = ToolRequest(
    agent_id="agent_001",
    tool_name="document_reader",
    arguments={"document_id": "report_01"},
    source="user_request",
    task_id="validation_001"
)

# Test 2: Unexpected argument
invalid_request = ToolRequest(
    agent_id="agent_001",
    tool_name="document_reader",
    arguments={
        "document_id": "report_01",
        "admin_access": True
    },
    source="user_request",
    task_id="validation_002"
)

# Test 3: Missing required argument
missing_request = ToolRequest(
    agent_id="agent_001",
    tool_name="file_search",
    arguments={},
    source="user_request",
    task_id="validation_003"
)

print("\nTEST 1: Valid arguments")
print(execute_tool(valid_request))

print("\nTEST 2: Unexpected argument")
print(execute_tool(invalid_request))

print("\nTEST 3: Missing argument")
print(execute_tool(missing_request))
