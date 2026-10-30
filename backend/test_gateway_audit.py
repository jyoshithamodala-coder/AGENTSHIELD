
from app.models.schemas import ToolRequest
from app.security.gateway import execute_tool
from app.audit.logger import get_audit_logs


request = ToolRequest(
    agent_id="agent_001",
    tool_name="document_reader",
    arguments={
        "document_id": "report_01"
    },
    source="user_request",
    task_id="audit_test_001"
)

response = execute_tool(request)

print("\nGateway response:")
print(response)

print("\nLatest audit records:")
for log in get_audit_logs(limit=5):
    print(log)
