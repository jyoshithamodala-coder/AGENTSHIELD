
from langchain_core.messages import HumanMessage
from app.agent.graph import agent_graph

result = agent_graph.invoke({
    "messages": [
        HumanMessage(
            content="Explain what AgentShield does in two sentences."
        )
    ]
})

print("\nAgentShield response:")
print(result["messages"][-1].content)
