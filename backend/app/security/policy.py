
from app.models.schemas import SecurityDecision


# Define the tools available to our agent
TOOL_PERMISSIONS = {
    "document_reader": ["read"],
    "file_search": ["search"],
    "sensitive_data": [],
    "external_communication": [],
    "file_access_manager": [],
    "database_manager": []
}


def evaluate_policy(tool_name: str, user_confirmed: bool = False):

    # Unknown tools are always denied
    if tool_name not in TOOL_PERMISSIONS:
        return {
            "decision": SecurityDecision.DENY,
            "reason": "Unknown tool. Access denied.",
            "risk_level": "HIGH"
        }

    # External communication requires explicit approval
    if tool_name == "external_communication":
        if not user_confirmed:
            return {
                "decision": SecurityDecision.REQUIRE_APPROVAL,
                "reason": "External communication requires user approval.",
                "risk_level": "HIGH"
            }

    # Sensitive data access is not permitted
    if tool_name == "sensitive_data":
        return {
            "decision": SecurityDecision.DENY,
            "reason": "Sensitive data access is not permitted.",
            "risk_level": "HIGH"
        }

    return {
        "decision": SecurityDecision.ALLOW,
        "reason": "Tool is authorized by security policy.",
        "risk_level": "LOW"
    }
