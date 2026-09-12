"""Handoff envelope for inter-worker context transfer.

When execution transitions from one worker to another (e.g., browser -> API),
the handoff envelope carries all necessary context WITHOUT raw secrets.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from webcmd.state.enums import HandoffStatus, HandoffReason, RiskLevel


class HandoffEnvelope(BaseModel):
    """Complete handoff context package.
    
    Supports BOTH target_worker_type (category routing) and
    target_worker_id (instance routing) to resolve the cross-doc
    inconsistency between DATA_MODEL and HANDOFF_PROTOCOL.
    """
    handoff_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    source_worker_run_id: UUID
    
    # Target - supports both type (category) and id (instance)
    target_worker_type: str = Field(description="Worker type for capability routing")
    target_worker_id: UUID | None = Field(default=None, description="Specific worker instance if known")
    
    # Context
    reason: HandoffReason
    required_capabilities: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    
    # Payload (never contains raw secrets)
    context_data: dict[str, Any] = Field(default_factory=dict)
    input_bindings: dict[str, Any] = Field(default_factory=dict)
    environment_state: dict[str, Any] = Field(default_factory=dict)
    
    # Credential references (opaque vault keys only)
    credential_refs: dict[str, str] = Field(
        default_factory=dict,
        description="Map of logical name to vault reference"
    )
    
    # Session bridge reference
    session_ref: str | None = Field(
        default=None,
        description="Opaque session reference for the SessionBridge"
    )
    
    # Lifecycle
    status: HandoffStatus = HandoffStatus.REQUESTED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Verification
    source_verification_passed: bool = Field(
        default=False,
        description="Whether the source worker's last step passed verification"
    )
    revalidation_criteria: list[str] = Field(
        default_factory=list,
        description="Conditions the target must verify before proceeding"
    )
