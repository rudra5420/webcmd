"""Handoff Manager for WebCMD.

Manages the lifecycle of worker-to-worker handoffs.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from webcmd.handoff.envelope import HandoffEnvelope
from webcmd.handoff.session_bridge import SessionBridge
from webcmd.state.enums import HandoffStatus, HandoffReason
from webcmd.workers.registry import WorkerRegistry

logger = logging.getLogger(__name__)


class HandoffManager:
    """Manages worker-to-worker handoff lifecycle."""
    
    def __init__(
        self,
        worker_registry: WorkerRegistry,
        session_bridge: SessionBridge | None = None,
    ) -> None:
        self.registry = worker_registry
        self.session_bridge = session_bridge or SessionBridge()
        self._pending: dict[UUID, HandoffEnvelope] = {}
    
    async def initiate_handoff(
        self,
        execution_id: UUID,
        source_worker_run_id: UUID,
        target_worker_type: str,
        reason: HandoffReason,
        context_data: dict[str, Any] | None = None,
        required_capabilities: list[str] | None = None,
        session_data: dict[str, Any] | None = None,
    ) -> HandoffEnvelope:
        """Initiate a handoff from one worker to another."""
        # Create session ref if session data provided
        session_ref = None
        if session_data:
            session_ref = self.session_bridge.create_session_ref(session_data)
        
        envelope = HandoffEnvelope(
            execution_id=execution_id,
            source_worker_run_id=source_worker_run_id,
            target_worker_type=target_worker_type,
            reason=reason,
            required_capabilities=required_capabilities or [],
            context_data=context_data or {},
            session_ref=session_ref,
        )
        
        self._pending[envelope.handoff_id] = envelope
        logger.info(f"Handoff initiated: {envelope.handoff_id} -> {target_worker_type}")
        return envelope
    
    async def validate_handoff(
        self, handoff_id: UUID
    ) -> tuple[bool, str]:
        """Validate that the target worker can accept the handoff."""
        envelope = self._pending.get(handoff_id)
        if not envelope:
            return False, "Handoff not found"
        
        # Check target worker exists
        registered = self.registry.list_registered()
        if envelope.target_worker_type not in registered:
            return False, f"Target worker type '{envelope.target_worker_type}' not registered"
        
        # Check capabilities
        if envelope.required_capabilities:
            caps = await self.registry.get_capabilities(envelope.target_worker_type)
            missing = [c for c in envelope.required_capabilities if not caps.has(c)]
            if missing:
                return False, f"Target missing capabilities: {missing}"
        
        envelope.status = HandoffStatus.VALIDATED
        return True, "Handoff validated"
    
    async def accept_handoff(
        self, handoff_id: UUID
    ) -> HandoffEnvelope | None:
        """Accept and transition a handoff."""
        envelope = self._pending.get(handoff_id)
        if not envelope:
            return None
        
        envelope.status = HandoffStatus.ACCEPTED
        envelope.accepted_at = datetime.now(timezone.utc)
        logger.info(f"Handoff accepted: {handoff_id}")
        return envelope
    
    async def complete_handoff(
        self, handoff_id: UUID
    ) -> HandoffEnvelope | None:
        """Mark a handoff as completed."""
        envelope = self._pending.pop(handoff_id, None)
        if not envelope:
            return None
        
        envelope.status = HandoffStatus.COMPLETED
        envelope.completed_at = datetime.now(timezone.utc)
        
        # Revoke session ref after completion
        if envelope.session_ref:
            self.session_bridge.revoke_session_ref(envelope.session_ref)
        
        logger.info(f"Handoff completed: {handoff_id}")
        return envelope
    
    async def reject_handoff(
        self, handoff_id: UUID, reason: str = ""
    ) -> HandoffEnvelope | None:
        envelope = self._pending.pop(handoff_id, None)
        if not envelope:
            return None
        envelope.status = HandoffStatus.REJECTED
        logger.info(f"Handoff rejected: {handoff_id} - {reason}")
        return envelope
