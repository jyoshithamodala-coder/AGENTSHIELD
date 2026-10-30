
from app.audit.logger import (
    initialize_audit_db,
    log_security_event,
    get_audit_logs
)

initialize_audit_db()

log_security_event(
    task_id="task_demo_001",
    agent_id="agent_001",
    tool_name="document_reader",
    decision="ALLOW",
    reason="Document reading is permitted.",
    risk_level="LOW",
    arguments={"document_id": "report_01"}
)

logs = get_audit_logs()

print("Audit log test successful!")
print(logs)
