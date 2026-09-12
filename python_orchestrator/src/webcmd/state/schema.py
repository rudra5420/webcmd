from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID, uuid4

class SecurityState(BaseModel):
    """Represents the current security posture."""
    active_policies: List[str] = Field(default_factory=list)
    escalations: List[str] = Field(default_factory=list)
    credentials_accessed: List[str] = Field(default_factory=list)

class VerificationSummary(BaseModel):
    """Summary of verification state."""
    is_verified: bool = False
    confidence_score: float = 0.0
    last_verified_at: Optional[datetime] = None
    verification_errors: List[str] = Field(default_factory=list)

class EnvironmentState(BaseModel):
    """Current state of the execution environment."""
    url: Optional[str] = None
    dom_hash: Optional[str] = None
    session_refs: Dict[str, str] = Field(default_factory=dict)
    local_files: List[str] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)

class StepState(BaseModel):
    """Projection of a single step's state."""
    step_id: UUID
    name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    verification: VerificationSummary = Field(default_factory=VerificationSummary)
    environment_snapshot: Optional[EnvironmentState] = None

class ExecutionState(BaseModel):
    """Projection of an execution's state."""
    execution_id: UUID
    project_id: UUID
    status: str
    recovery_status: str = "NONE"
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_id: Optional[UUID] = None
    steps: Dict[UUID, StepState] = Field(default_factory=dict)
    environment: EnvironmentState = Field(default_factory=EnvironmentState)
    security: SecurityState = Field(default_factory=SecurityState)
    context_data: Dict[str, Any] = Field(default_factory=dict)

class ProjectState(BaseModel):
    """High-level projection of a project."""
    project_id: UUID
    name: str
    active_executions: List[UUID] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    variables: Dict[str, Any] = Field(default_factory=dict)

class LastKnownState(BaseModel):
    """Snapshot of the last stable state for recovery."""
    checkpoint_id: UUID
    execution_id: UUID
    timestamp: datetime
    execution_state: ExecutionState
