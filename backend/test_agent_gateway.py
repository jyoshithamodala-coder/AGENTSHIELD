
from langchain_core.messages import HumanMessage

from app.models.schemas import ToolRequest
from app.agent.graph import agent_graph


# User asks the agent to read a synthetic document.
request = ToolRequest(
    agent_id="agent_001",
    tool_name="document_reader",
    arguments={
        "document_id": "report_01"
    },
    source="user_request",
    task_id="agent_gateway_test_001"
)


result = agent_graph.invoke({
    "messages": [
        HumanMessage(
            content="Read the project report and explain what AgentShield does."
        )
    ],
    "tool_request": request,
    "security_result": None
})

request = ToolRequest(
    agent_id="agent_001",
    tool_name="external_communication",
    arguments={
        "destination": "demo@example.test",
        "content": "AgentShield approval test."
    },
    source="user_request",
    task_id="agent_approval_test_001"
)


print("\nSECURITY GATEWAY RESULT:")
print(result["security_result"])

print("\nFINAL AI RESPONSE:")
print(result["messages"][-1].content)
