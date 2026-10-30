
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SecurityDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=1)
    document_id: Optional[str] = None


class ToolRequest(BaseModel):
    agent_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    source: str
    task_id: Optional[str] = None


class SecurityResponse(BaseModel):
    decision: SecurityDecision
    reason: str
    executed: bool = False
    result: Any = None
    risk_level: str = "UNKNOWN"
    approval_id: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    response: str
    security: SecurityResponse


class ApprovalRequest(BaseModel):
    approval_id: str = Field(..., min_length=1)


class ApprovalDecisionRequest(BaseModel):
    approval_id: str = Field(..., min_length=1)
    approved: bool
