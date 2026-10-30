
# Synthetic document storage

DOCUMENTS = {
    "report_01": {
        "title": "Project Report",
        "content": """
        AgentShield is an AI agent security project.

        It protects AI agents from malicious instructions
        and unauthorized tool operations.

        The project uses a security gateway to validate
        every tool request.
        """
    },

    "report_02": {
        "title": "Security Notes",
        "content": """
        AI security requires proper permission management.

        Every tool operation should be checked before execution.
        """
    }
}


def read_document(document_id: str):

    document = DOCUMENTS.get(document_id)

    if not document:
        return {
            "success": False,
            "message": "Document not found"
        }

    return {
        "success": True,
        "title": document["title"],
        "content": document["content"]
    }
