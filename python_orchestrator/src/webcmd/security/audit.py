"""Append-only audit logger for WebCMD.

Records all security-relevant events in a tamper-evident log.
The audit log is immutable — entries can only be appended.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditEntry(BaseModel):
    """A single audit log entry."""
    audit_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    execution_id: UUID | None = None
    actor: str = "system"
    action: str = ""
    resource: str = ""
    decision: str = ""
    reason: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class AuditLogger:
    """Append-only audit log writer."""
    
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, entry: AuditEntry) -> None:
        """Append an audit entry."""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
    
    def log_policy_decision(
        self,
        execution_id: UUID | None,
        capability: str,
        resource: str,
        decision: str,
        reason: str,
    ) -> None:
        self.log(AuditEntry(
            event_type="policy_decision",
            execution_id=execution_id,
            action=capability,
            resource=resource,
            decision=decision,
            reason=reason,
        ))
    
    def log_approval(
        self,
        execution_id: UUID,
        action: str,
        decision: str,
        approved_by: str,
    ) -> None:
        self.log(AuditEntry(
            event_type="approval",
            execution_id=execution_id,
            actor=approved_by,
            action=action,
            decision=decision,
        ))
    
    def log_credential_access(
        self,
        execution_id: UUID | None,
        credential_ref: str,
        action: str,
    ) -> None:
        self.log(AuditEntry(
            event_type="credential_access",
            execution_id=execution_id,
            action=action,
            resource=credential_ref,
        ))

    def log_human_verification(
        self,
        execution_id: UUID,
        status: str,
        verified_by: str = "human",
        reason: str = "",
        automated_verification: str = "PASS",
    ) -> None:
        """Record human verification outcome in append-only audit log."""
        self.log(AuditEntry(
            event_type="human_verification",
            execution_id=execution_id,
            actor=verified_by,
            action="verify_final_result",
            decision=status.upper(),
            reason=reason,
            details={
                "automated_verification": automated_verification,
                "human_verification_result": status.upper(),
            },
        ))
    
    def get_entries(
        self, execution_id: UUID | None = None, limit: int = 100
    ) -> list[AuditEntry]:
        """Read audit entries (for inspection only)."""
        if not self.log_path.exists():
            return []
        
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = AuditEntry.model_validate_json(line)
                    if execution_id is None or entry.execution_id == execution_id:
                        entries.append(entry)
                except Exception:
                    continue
        
        return entries[-limit:]
