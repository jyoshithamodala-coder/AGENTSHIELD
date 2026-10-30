
from app.agent.planner import plan_user_action


test_prompts = [
    "Read report 01",
    "Search for security",
    "Show employee information",
    "Send an email to demo@example.test saying AgentShield is ready.",
    "Hello, what is AgentShield?"
]

for prompt in test_prompts:
    print("\nUser:", prompt)

    result = plan_user_action(prompt)

    if result:
        print("Tool:", result.tool_name)
        print("Arguments:", result.arguments)
    else:
        print("Tool: No tool required")
