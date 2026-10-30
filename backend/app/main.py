import uuid

from langchain_core.messages import HumanMessage
from app.agent.graph import agent_graph
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import (
    ToolRequest,
    TaskRequest,
    ApprovalDecisionRequest
)

from app.security.gateway import (
    execute_tool,
    resolve_approval,
    execute_approved_tool
)

from app.audit.logger import (
    initialize_audit_db,
    get_audit_logs
)


app = FastAPI(
    title="AgentShield API",
    description="AI Agent Security Gateway",
    version="1.0.0"
)


# Frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    initialize_audit_db()


@app.get("/")
def home():
    return {
        "message": "Welcome to AgentShield",
        "status": "running"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": "AgentShield",
        "version": "1.0.0"
    }


# 1. Submit a tool request
@app.post("/api/tools/execute")
def api_execute_tool(request: ToolRequest):
    try:
        return execute_tool(request)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Tool request could not be processed safely."
        )


# 2. Approve or reject a pending action
@app.post("/api/approvals/{approval_id}/resolve")
def api_resolve_approval(
    approval_id: str,
    request: ApprovalDecisionRequest
):
    if request.approval_id != approval_id:
        raise HTTPException(
            status_code=400,
            detail="Approval ID mismatch."
        )

    try:
        success, message = resolve_approval(
            approval_id,
            request.approved
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail=message
            )

        return {
            "success": True,
            "approval_id": approval_id,
            "message": message
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Approval could not be processed."
        )


# 3. Execute an approved action
@app.post("/api/approvals/{approval_id}/execute")
def api_execute_approved_action(approval_id: str):
    try:
        return execute_approved_tool(approval_id)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Approved action could not be executed safely."
        )


# 4. Retrieve audit history
@app.get("/api/audit")
def api_get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200)
):
    try:
        return {
            "success": True,
            "count": len(get_audit_logs(limit)),
            "logs": get_audit_logs(limit)
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Audit history is currently unavailable."
        )


@app.post("/api/tasks")
def create_task(request: TaskRequest):
    task_id = str(uuid.uuid4())

    try:
        result = agent_graph.invoke({
            "messages": [
                HumanMessage(content=request.task)
            ],
            "tool_request": None,
            "security_result": None,
            "task_id": task_id
        })

        security = result.get("security_result")

        if security is not None:
            security_decision = security["decision"]

            if hasattr(security_decision, "value"):
                security_decision = security_decision.value

            security = {
                **security,
                "decision": security_decision
            }

        return {
            "task_id": task_id,
            "response": result["messages"][-1].content,
            "security": security
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Agent task could not be processed."
        )
