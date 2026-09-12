"""Checkpoint models for WebCMD state persistence."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from webcmd.state.enums import CheckpointTrigger, VerificationStatus


class ResumeBoundary(BaseModel):
    """Rich resume boundary - declares what's safe to resume from.
    
    This resolves the cross-document inconsistency where
    PROJECT_STATE_SCHEMA defined this as string|null but
    CHECKPOINT_DESIGN specified a 6-field object.
    """
    last_verified_step_id: UUID | None = None
    next_step_id: UUID | None = None
    uncertain_side_effects: list[dict[str, Any]] = Field(default_factory=list)
    revalidation_criteria: list[str] = Field(
        default_factory=list,
        description="Environment assumptions to test before resuming"
    )
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)


class LogicalCheckpoint(BaseModel):
    """What the workflow believes happened."""
    completed_steps: list[UUID] = Field(default_factory=list)
    pending_steps: list[UUID] = Field(default_factory=list)
    current_step_id: UUID | None = None
    variable_bindings: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


class EnvironmentalCheckpoint(BaseModel):
    """What the external system looked like."""
    url: str | None = None
    dom_fingerprint: str | None = None
    session_refs: list[str] = Field(default_factory=list)
    open_files: list[str] = Field(default_factory=list)
    environment_hash: str | None = None


class EvidenceCheckpoint(BaseModel):
    """References to collected proof."""
    observation_ids: list[UUID] = Field(default_factory=list)
    artifact_ids: list[UUID] = Field(default_factory=list)
    screenshot_paths: list[str] = Field(default_factory=list)
    evidence_hash: str | None = None


class RecoveryCheckpoint(BaseModel):
    """Recovery state at checkpoint time."""
    attempt_counts: dict[str, int] = Field(default_factory=dict)
    failure_codes: list[str] = Field(default_factory=list)
    remaining_budget: dict[str, int] = Field(default_factory=dict)


class CheckpointData(BaseModel):
    """Complete 4-layer checkpoint."""
    checkpoint_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    sequence_number: int = 0
    trigger: CheckpointTrigger
    
    # 4 layers
    logical: LogicalCheckpoint = Field(default_factory=LogicalCheckpoint)
    environmental: EnvironmentalCheckpoint = Field(default_factory=EnvironmentalCheckpoint)
    evidence: EvidenceCheckpoint = Field(default_factory=EvidenceCheckpoint)
    recovery: RecoveryCheckpoint = Field(default_factory=RecoveryCheckpoint)
    
    # Resume info
    resume_boundary: ResumeBoundary = Field(default_factory=ResumeBoundary)
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    
    # Integrity
    state_hash: str | None = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
