"""Worker type definitions for the WebCMD execution plane."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from webcmd.state.enums import (
    IdempotencyType,
    RiskLevel,
    SideEffectStatus,
    TrustLevel,
)


class Capability(BaseModel):
    """A single worker capability."""
    name: str = Field(description="Hierarchical capability name, e.g. 'browser.navigate'")
    description: str = Field(default="")
    idempotency: IdempotencyType = Field(default=IdempotencyType.UNKNOWN)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)


class CapabilitySet(BaseModel):
    """Set of capabilities a worker supports."""
    capabilities: list[Capability] = Field(default_factory=list)
    
    def has(self, name: str) -> bool:
        """Check if capability exists."""
        return any(c.name == name for c in self.capabilities)
    
    def get(self, name: str) -> Capability | None:
        """Get a specific capability."""
        return next((c for c in self.capabilities if c.name == name), None)
    
    def names(self) -> set[str]:
        """Get all capability names."""
        return {c.name for c in self.capabilities}


class WorkerContext(BaseModel):
    """Scoped execution context passed to a worker.
    
    Contains everything a worker needs to execute a step
    without accessing global state.
    """
    execution_id: UUID
    step_id: UUID
    worker_run_id: UUID
    
    # What this worker is allowed to do
    allowed_capabilities: list[str] = Field(default_factory=list)
    
    # Input data for this step
    input_bindings: dict[str, Any] = Field(default_factory=dict)
    
    # Environment hints
    environment: dict[str, Any] = Field(default_factory=dict)
    
    # Memory hints from the learning system
    memory_hints: dict[str, Any] = Field(default_factory=dict)
    
    # Execution constraints
    time_budget_s: float = Field(default=300.0, description="Max seconds for this step")
    attempt_number: int = Field(default=1)
    
    # Credential references (never raw secrets)
    credential_refs: dict[str, str] = Field(
        default_factory=dict,
        description="Map of logical name to vault reference, e.g. {'github': 'vault://github_creds'}"
    )


class PreparedAction(BaseModel):
    """A validated, execution-ready action unit."""
    action_id: UUID = Field(default_factory=uuid4)
    worker_type: str
    capability: str
    target: str = Field(default="", description="Target resource/URL/path")
    parameters: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    expected_postconditions: list[str] = Field(default_factory=list)
    idempotency: IdempotencyType = Field(default=IdempotencyType.UNKNOWN)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)


class ObservationRecord(BaseModel):
    """An observation emitted by a worker during execution."""
    observation_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trust_class: TrustLevel = Field(default=TrustLevel.T4_TOOL_OUTPUT)


class WorkerResult(BaseModel):
    """Standardized result from worker execution.
    
    Workers report what happened. They do NOT verify correctness.
    Verification is handled by the central VerificationEngine.
    """
    status: str = Field(description="succeeded | failed | cancelled | blocked | uncertain")
    outputs: dict[str, Any] = Field(default_factory=dict)
    observations: list[ObservationRecord] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    failure_code: str | None = Field(default=None)
    failure_message: str | None = Field(default=None)
    retryable: bool = Field(default=False)
    side_effect_status: SideEffectStatus = Field(default=SideEffectStatus.NONE)
    duration_ms: float = Field(default=0.0)


class PauseResult(BaseModel):
    """Result of pausing a worker."""
    success: bool
    state_snapshot: dict[str, Any] = Field(default_factory=dict)


class ResumeResult(BaseModel):
    """Result of resuming a worker."""
    success: bool
    message: str = Field(default="")
