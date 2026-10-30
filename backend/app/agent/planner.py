
import re

from app.models.schemas import ToolRequest


def plan_user_action(user_message: str, task_id=None):
    """
    Controlled action planner.

    Identifies supported user intents and creates a ToolRequest.
    It does not execute tools.
    """

    message = user_message.strip()
    lower_message = message.lower()

    # 1. Document reading
    document_match = re.search(
        r"\b(?:report|document)\s*[_#-]?(\d+)\b",
        lower_message
    )

    if document_match and any(
        word in lower_message
        for word in ["read", "open", "summarize", "show", "review"]
    ):
        document_id = f"report_{int(document_match.group(1)):02d}"

        return ToolRequest(
            agent_id="agent_001",
            tool_name="document_reader",
            arguments={"document_id": document_id},
            source="user_request",
            task_id=task_id
        )

    # 2. File search
    search_match = re.search(
        r"\b(?:search|find|look for)\s+(?:files?\s+)?(?:for\s+)?(.+)",
        message,
        re.IGNORECASE
    )

    if search_match:
        keyword = search_match.group(1).strip(" .?!")

        if keyword:
            return ToolRequest(
                agent_id="agent_001",
                tool_name="file_search",
                arguments={"keyword": keyword[:100]},
                source="user_request",
                task_id=task_id
            )

    # 3. Sensitive data access
    if any(
        phrase in lower_message
        for phrase in [
            "employee information",
            "employee record",
            "sensitive data",
            "personal information"
        ]
    ):
        return ToolRequest(
            agent_id="agent_001",
            tool_name="sensitive_data",
            arguments={"record_id": "employee_01"},
            source="user_request",
            task_id=task_id
        )

    # 4. External communication
    if any(
        word in lower_message
        for word in ["send message", "send an email", "send email"]
    ):
        email_match = re.search(
            r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            message
        )

        if email_match:
            destination = email_match.group(0)

            content_match = re.search(
                r"(?:saying|message|content)\s*[:\-]?\s*[\"']?(.+)",
                message,
                re.IGNORECASE
            )

            content = (
                content_match.group(1).strip(" \"'")
                if content_match
                else "User requested an external communication."
            )

            return ToolRequest(
                agent_id="agent_001",
                tool_name="external_communication",
                arguments={
                    "destination": destination,
                    "content": content[:2000]
                },
                source="user_request",
                task_id=task_id
            )

    # No supported action found.
    return None
