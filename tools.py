# tools.py

OPERATION_REGISTRY = {
    "calculator": {
        "description": "Evaluate a basic arithmetic expression.",
        "roles": {"user", "admin"},
        "required_arguments": {"expression"},
        "optional_arguments": set(),
        "risk": "LOW",
    },
    "save_note": {
        "description": "Save a private note for the logged-in user.",
        "roles": {"user", "admin"},
        "required_arguments": {"title", "content"},
        "optional_arguments": set(),
        "risk": "LOW",
    },
    "list_notes": {
        "description": "List the logged-in user's private notes.",
        "roles": {"user", "admin"},
        "required_arguments": set(),
        "optional_arguments": set(),
        "risk": "LOW",
    },
    "read_note": {
        "description": "Read a private note belonging to the logged-in user.",
        "roles": {"user", "admin"},
        "required_arguments": {"note_id"},
        "optional_arguments": set(),
        "risk": "LOW",
    },
    "delete_note": {
        "description": "Delete a private note. Requires explicit confirmation.",
        "roles": {"admin"},
        "required_arguments": {"note_id"},
        "optional_arguments": set(),
        "risk": "HIGH",
    },
}

# Descriptions supplied to Gemini to help it plan.
TOOL_DESCRIPTIONS = {
    name: details["description"]
    for name, details in OPERATION_REGISTRY.items()
}