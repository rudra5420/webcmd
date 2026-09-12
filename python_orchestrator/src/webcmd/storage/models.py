"""WebCMD domain models.

Contains all core entities for the WebCMD runtime, with strict
Pydantic v2 validation. All models represent immutable state or
records used by the state machine.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from webcmd.state.enums import (
    ProjectStatus, TaskStatus, ExecutionStatus, StepStatus,
    VerificationStatus, RecoveryStatus, WorkflowStatus, WorkerRunStatus,
    HandoffStatus, HandoffReason, FailureClass, RiskLevel, SideEffectStatus,
    IdempotencyType, MemoryType, MemoryStatus, TrustLevel, PolicyDecision,
    ApprovalDecision, CheckpointTrigger, ObservationType, AssertionType,
    HumanVerificationDecision
)


def get_utc_now() -> datetime:
    """Helper to return current UTC datetime."""
    return datetime.now(timezone.utc)


class BaseDomainModel(BaseModel):
    """Base model for domain objects."""
    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)


class Project(BaseDomainModel):
    """Represents a discrete webcmd project/workspace."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique project ID")
    name: str = Field(..., description="Project name")
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE, description="Current project status")
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")


class IntentSpec(BaseDomainModel):
    """Represents the parsed intent from user request."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: Optional[uuid.UUID] = None
    original_prompt: str = Field(default="", description="Raw user prompt")
    original_text: str = Field(default="", description="Alias for original prompt")
    objective: str = Field(default="", description="Actionable objective")
    parsed_goals: List[str] = Field(default_factory=list, description="Extracted actionable goals")
    constraints: List[str] = Field(default_factory=list, description="User constraints")
    inputs: Dict[str, Any] = Field(default_factory=dict)
    desired_outputs: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    created_at: datetime = Field(default_factory=get_utc_now)

    def model_post_init(self, __context: Any) -> None:
        if not self.original_prompt and self.original_text:
            self.original_prompt = self.original_text
        elif not self.original_text and self.original_prompt:
            self.original_text = self.original_prompt

    @property
    def intent_id(self) -> uuid.UUID:
        return self.id


class Task(BaseDomainModel):
    """Represents a high-level task to be executed."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Project this task belongs to")
    intent_spec_id: Optional[uuid.UUID] = Field(default=None, description="The intent specification for this task")
    intent_id: Optional[uuid.UUID] = Field(default=None, description="Alias for intent_spec_id")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: int = Field(default=1)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.intent_spec_id and self.intent_id:
            self.intent_spec_id = self.intent_id
        elif not self.intent_id and self.intent_spec_id:
            self.intent_id = self.intent_spec_id

    @property
    def task_id(self) -> uuid.UUID:
        return self.id


class Workflow(BaseDomainModel):
    """A series of operations or steps."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(..., description="Workflow name")
    description: str = Field(default="", description="Workflow description")
    status: WorkflowStatus = Field(default=WorkflowStatus.DRAFT)
    project_id: uuid.UUID = Field(..., description="Parent project")
    active_version_id: Optional[uuid.UUID] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    @property
    def workflow_id(self) -> uuid.UUID:
        return self.id


class WorkflowVersion(BaseDomainModel):
    """Immutable version of a workflow."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    workflow_id: uuid.UUID = Field(...)
    version: int = Field(default=1, description="Sequential version number")
    created_at: datetime = Field(default_factory=get_utc_now)
    step_ids: List[uuid.UUID] = Field(default_factory=list, description="Ordered steps in this version")

    @property
    def workflow_version_id(self) -> uuid.UUID:
        return self.id


class VerificationSpec(BaseDomainModel):
    """Specification of verification assertions to evaluate."""
    assertions: List[Dict[str, Any]] = Field(default_factory=list, description="List of assertion details")


class Step(BaseDomainModel):
    """A single logical step in an execution or workflow."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(..., description="Step name")
    description: str = Field(default="", description="Step details")
    sequence: int = Field(default=1)
    objective: str = Field(default="")
    required_capabilities: List[str] = Field(default_factory=list)
    action_spec: Dict[str, Any] = Field(default_factory=dict)
    preconditions: List[str] = Field(default_factory=list)
    workflow_version_id: Optional[uuid.UUID] = Field(default=None, description="Null for ad-hoc steps")
    execution_id: Optional[uuid.UUID] = Field(default=None, description="Optional associated execution")
    status: StepStatus = Field(default=StepStatus.PENDING)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    verification_spec: Optional[Any] = Field(default=None)
    retry_policy: Optional[Any] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    @property
    def step_id(self) -> uuid.UUID:
        return self.id


class HumanVerificationMetadata(BaseDomainModel):
    """Metadata for the single final human verification gate."""
    required: bool = True
    status: HumanVerificationDecision = HumanVerificationDecision.PENDING
    requested_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    reason: Optional[str] = None


class Execution(BaseDomainModel):
    """An execution instance of a Task or Workflow."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: Optional[uuid.UUID] = Field(default=None)
    project_id: Optional[uuid.UUID] = Field(default=None)
    workflow_version_id: Optional[uuid.UUID] = Field(default=None)
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
    current_step_id: Optional[uuid.UUID] = Field(default=None)
    current_worker_run_id: Optional[uuid.UUID] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    result: Optional[Any] = Field(default=None)
    failure_code: Optional[str] = Field(default=None)
    human_verification: Optional[HumanVerificationMetadata] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def execution_id(self) -> uuid.UUID:
        return self.id


class WorkerRegistration(BaseDomainModel):
    """Metadata for a registered worker."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(..., description="Worker identifier or name")
    capabilities: List[str] = Field(default_factory=list, description="Worker capabilities")
    created_at: datetime = Field(default_factory=get_utc_now)

    @property
    def worker_id(self) -> uuid.UUID:
        return self.id


class WorkerRun(BaseDomainModel):
    """Execution context for a worker on a step."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    worker_id: uuid.UUID = Field(..., description="Worker Registration ID")
    step_id: uuid.UUID = Field(...)
    execution_id: uuid.UUID = Field(...)
    status: WorkerRunStatus = Field(default=WorkerRunStatus.CREATED)
    attempt_number: int = Field(default=1)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    result: Optional[Any] = Field(default=None)
    failure_code: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    @property
    def worker_run_id(self) -> uuid.UUID:
        return self.id


class Observation(BaseDomainModel):
    """Worker observation item (immutable)."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    worker_run_id: uuid.UUID = Field(...)
    type: ObservationType = Field(...)
    data: Dict[str, Any] = Field(default_factory=dict, description="Observation payload")
    created_at: datetime = Field(default_factory=get_utc_now)


class Assertion(BaseDomainModel):
    """An evaluated verification assertion (immutable)."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    step_id: uuid.UUID = Field(...)
    type: AssertionType = Field(...)
    status: VerificationStatus = Field(default=VerificationStatus.UNKNOWN)
    result_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)


class ResumeBoundary(BaseDomainModel):
    """Defines safe resume criteria within a checkpoint."""
    last_verified_step_id: Optional[uuid.UUID] = Field(default=None)
    next_step_id: Optional[uuid.UUID] = Field(default=None)
    uncertain_side_effects: bool = Field(default=False)
    revalidation_criteria: Dict[str, Any] = Field(default_factory=dict)
    policy_snapshot: Dict[str, Any] = Field(default_factory=dict)
    required_capabilities: List[str] = Field(default_factory=list)


class Checkpoint(BaseDomainModel):
    """Snapshot of execution state (immutable)."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    execution_id: uuid.UUID = Field(...)
    trigger: CheckpointTrigger = Field(...)
    resume_boundary: ResumeBoundary = Field(...)
    created_at: datetime = Field(default_factory=get_utc_now)
    state_data: Dict[str, Any] = Field(default_factory=dict)


class HandoffRecord(BaseDomainModel):
    """Record of a task handoff (immutable)."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_worker_id: uuid.UUID = Field(...)
    target_worker_id: uuid.UUID = Field(...)
    execution_id: uuid.UUID = Field(...)
    reason: HandoffReason = Field(...)
    status: HandoffStatus = Field(default=HandoffStatus.REQUESTED)
    created_at: datetime = Field(default_factory=get_utc_now)


class RetryPolicy(BaseDomainModel):
    """Policy for retrying actions."""
    max_attempts: int = Field(default=3)
    backoff_base_s: int = Field(default=1)
    backoff_max_s: int = Field(default=60)
    retryable_failures: List[FailureClass] = Field(default_factory=list)


class RecoveryAttempt(BaseDomainModel):
    """Record of a recovery sequence (immutable)."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    execution_id: uuid.UUID = Field(...)
    step_id: uuid.UUID = Field(...)
    failure_class: FailureClass = Field(...)
    status: RecoveryStatus = Field(default=RecoveryStatus.NEEDED)
    retry_policy: Optional[RetryPolicy] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)


class Artifact(BaseDomainModel):
    """File or resource produced by the system."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(...)
    name: str = Field(...)
    path: str = Field(...)
    hash: str = Field(..., description="Content hash for integrity")
    created_at: datetime = Field(default_factory=get_utc_now)


class MemoryItem(BaseDomainModel):
    """Experiential memory record."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(...)
    type: MemoryType = Field(...)
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE)
    provenance: TrustLevel = Field(default=TrustLevel.T3_MODEL_OUTPUT)
    confidence: float = Field(default=1.0, description="Confidence score 0.0-1.0")
    data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class SiteProfile(BaseDomainModel):
    """Known domain/site characteristics."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    domain: str = Field(...)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class PolicyRule(BaseDomainModel):
    """Execution policy definition."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(...)
    condition: str = Field(...)
    decision: PolicyDecision = Field(...)
    created_at: datetime = Field(default_factory=get_utc_now)


class Approval(BaseDomainModel):
    """Record of user authorization."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    execution_id: uuid.UUID = Field(...)
    decision: ApprovalDecision = Field(...)
    action_hash: str = Field(..., description="Cryptographic binding of approved action")
    created_at: datetime = Field(default_factory=get_utc_now)


class AuditEvent(BaseDomainModel):
    """Immutable audit trail record."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    entity_id: uuid.UUID = Field(..., description="ID of the related entity")
    entity_type: str = Field(...)
    action: str = Field(...)
    timestamp: datetime = Field(default_factory=get_utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
