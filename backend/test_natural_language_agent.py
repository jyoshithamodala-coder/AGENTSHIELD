
from langchain_core.messages import HumanMessage
from app.agent.graph import agent_graph


prompts = [
    "Read report 01",
    "Show employee information",
    "Send an email to demo@example.test saying AgentShield is ready.",
    "Hello, what is AgentShield?"
]

for prompt in prompts:

    print("\n" + "=" * 55)
    print("USER:", prompt)

    result = agent_graph.invoke({
        "messages": [HumanMessage(content=prompt)],
        "tool_request": None,
        "security_result": None
    })

    print("\nSECURITY RESULT:")
    print(result["security_result"])

    print("\nAGENT RESPONSE:")
    print(result["messages"][-1].content)
