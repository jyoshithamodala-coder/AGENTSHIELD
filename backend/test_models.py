
from app.models.schemas import (
    TaskRequest,
    ToolRequest,
    SecurityResponse,
    SecurityDecision
)


def test_task_request():
    task = TaskRequest(
        task="Summarize my report",
        document_id="report_01"
    )

    assert task.task == "Summarize my report"


def test_tool_request():
    request = ToolRequest(
        agent_id="agent_01",
        tool_name="document_reader",
        arguments={"document_id": "report_01"},
        source="user_task"
    )

    assert request.tool_name == "document_reader"


def test_security_response():
    response = SecurityResponse(
        decision=SecurityDecision.ALLOW,
        reason="Authorized operation",
        executed=True
    )

    assert response.decision == SecurityDecision.ALLOW


if __name__ == "__main__":
    test_task_request()
    test_tool_request()
    test_security_response()

    print("All model tests passed!")
