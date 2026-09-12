"""Tests for the Single Final Human Verification Gate.

Tests A-F:
- Test A: Confirm flow (automated pass -> awaiting_human_verification -> confirm -> completed -> memory signal)
- Test B: Reject flow (automated pass -> awaiting_human_verification -> reject -> recovering -> audit & failure record)
- Test C: Restart while waiting (pre_human_verification checkpoint preserved -> restart -> resume without restart)
- Test D: No premature completion (no bypass, invalid transitions rejected)
- Test E: Learning distinction (human confirmed 0.95 confidence vs automated 0.70 vs rejection negative signal)
- Test F: Audit log (append-only audit entries for decisions with actor, reason, automated verification)
"""
import pytest
from pathlib import Path
from uuid import uuid4

from webcmd.config import WebCMDConfig
from webcmd.core.orchestrator import Orchestrator
from webcmd.memory.engine import MemoryEngine
from webcmd.security.audit import AuditLogger
from webcmd.state.enums import (
    CheckpointTrigger,
    ExecutionStatus,
    HumanVerificationDecision,
    MemoryType,
)
from webcmd.storage.database import DatabaseManager
from webcmd.workers.mock import MockWorker
from webcmd.workers.registry import WorkerRegistry


@pytest.fixture
async def env(tmp_path: Path):
    config = WebCMDConfig(home_dir=tmp_path / ".webcmd")
    config.ensure_dirs()
    
    db = DatabaseManager(config.get_db_path())
    await db.initialize()
    
    registry = WorkerRegistry()
    registry.register(MockWorker)
    
    orch = Orchestrator(config, db, registry)
    yield config, db, registry, orch
    await db.close()


class TestHumanVerificationGate:
    @pytest.mark.asyncio
    async def test_a_confirm_flow(self, env):
        """Test A: Automated pass -> AWAITING_HUMAN_VERIFICATION -> Confirm -> COMPLETED."""
        config, db, registry, orch = env
        
        # 1. Execute task - automated verification will succeed
        execution = await orch.execute_task("Generate report and upload")
        
        # 2. Assert execution paused at human gate, NOT completed
        assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
        assert execution.human_verification is not None
        assert execution.human_verification.required is True
        assert execution.human_verification.status == HumanVerificationDecision.PENDING
        assert execution.human_verification.requested_at is not None

        # 3. Assert pre-verification checkpoint was created
        checkpoints = await orch.checkpoint_mgr.get_all(execution.execution_id)
        assert len(checkpoints) >= 1
        latest_cp = checkpoints[-1]
        assert latest_cp.trigger == CheckpointTrigger.PRE_HUMAN_VERIFICATION

        # 4. Confirm execution as human operator
        confirmed = await orch.confirm_execution(
            execution.execution_id, verified_by="operator_alice"
        )
        assert confirmed.status == ExecutionStatus.COMPLETED
        assert confirmed.human_verification.status == HumanVerificationDecision.CONFIRMED
        assert confirmed.human_verification.verified_by == "operator_alice"
        assert confirmed.human_verification.completed_at is not None
        assert confirmed.finished_at is not None

        # 5. Check domain events
        events = await orch.event_store.get_events(execution.execution_id)
        event_types = [e.event_type for e in events]
        assert "HumanVerificationRequested" in event_types
        assert "HumanVerificationDecided" in event_types

        # 6. Check audit log
        audit_entries = orch.audit_logger.get_entries(execution.execution_id)
        hv_audits = [e for e in audit_entries if e.event_type == "human_verification"]
        assert len(hv_audits) == 1
        assert hv_audits[0].decision == "CONFIRMED"
        assert hv_audits[0].actor == "operator_alice"

    @pytest.mark.asyncio
    async def test_b_reject_flow(self, env):
        """Test B: Automated pass -> AWAITING_HUMAN_VERIFICATION -> Reject -> RECOVERING with reason."""
        config, db, registry, orch = env
        
        execution = await orch.execute_task("Scrape customer emails")
        assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION

        # Reject execution with specific feedback
        rejected = await orch.reject_execution(
            execution.execution_id,
            reason="Extracted company domains instead of personal emails",
            verified_by="supervisor_bob",
        )
        assert rejected.status == ExecutionStatus.RECOVERING
        assert rejected.human_verification.status == HumanVerificationDecision.REJECTED
        assert rejected.human_verification.verified_by == "supervisor_bob"
        assert "Extracted company domains" in rejected.human_verification.reason
        assert "HUMAN_REJECTED" in rejected.failure_code

        # Check audit log recorded rejection with reason
        audit_entries = orch.audit_logger.get_entries(execution.execution_id)
        hv_audits = [e for e in audit_entries if e.event_type == "human_verification"]
        assert len(hv_audits) == 1
        assert hv_audits[0].decision == "REJECTED"
        assert "Extracted company domains" in hv_audits[0].reason

    @pytest.mark.asyncio
    async def test_c_restart_while_waiting(self, env):
        """Test C: Checkpoint trigger PRE_HUMAN_VERIFICATION is preserved and restart maintains gate state."""
        config, db, registry, orch = env

        execution = await orch.execute_task("Long running batch workflow")
        assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION

        # Checkpoint trigger PRE_HUMAN_VERIFICATION is preserved
        checkpoints = await orch.checkpoint_mgr.get_all(execution.execution_id)
        pre_cp = next(cp for cp in checkpoints if cp.trigger == CheckpointTrigger.PRE_HUMAN_VERIFICATION)
        assert pre_cp is not None

        # Simulate process restart by creating a new Orchestrator instance pointing to same DB & config
        restarted_orch = Orchestrator(config, db, registry)
        
        # Retrieve execution from restarted orchestrator
        restored = await restarted_orch.get_execution(execution.execution_id)
        assert restored is not None
        # Must still be in AWAITING_HUMAN_VERIFICATION state (does not re-execute or crash)
        assert restored.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
        assert restored.human_verification.status == HumanVerificationDecision.PENDING

        # Process can now be resumed by confirming the restored execution
        confirmed = await restarted_orch.confirm_execution(
            restored.execution_id, verified_by="ops_recovery"
        )
        assert confirmed.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_d_no_premature_completion(self, env):
        """Test D: Execution cannot prematurely complete without explicit confirmation."""
        config, db, registry, orch = env

        execution = await orch.execute_task("Critical file transfer")
        # Direct verify that state is strictly AWAITING_HUMAN_VERIFICATION
        assert execution.status != ExecutionStatus.COMPLETED
        assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION

        # Attempting to confirm an execution with random UUID should fail cleanly
        with pytest.raises(ValueError, match="not found"):
            await orch.confirm_execution(uuid4())

        # Calling confirm on already completed execution should fail
        await orch.confirm_execution(execution.execution_id)
        with pytest.raises(ValueError, match="is not awaiting human verification"):
            await orch.confirm_execution(execution.execution_id)

    @pytest.mark.asyncio
    async def test_e_learning_distinction(self, env):
        """Test E: High confidence (0.95) for human confirmed vs (0.70) for automated vs negative for rejection."""
        config, db, registry, orch = env
        memory = orch.memory_engine
        pid = uuid4()
        eid_human = uuid4()
        eid_auto = uuid4()
        eid_reject = uuid4()

        # 1. Human verified execution -> strong positive signal (0.95 confidence)
        await memory.learn_from_execution(
            project_id=pid,
            execution_id=eid_human,
            domain="verified-target.com",
            url="https://verified-target.com/page",
            human_verified=True,
        )
        memories = await memory.store.query(pid, scope_key="verified-target.com")
        assert len(memories) >= 1
        assert memories[0]["confidence"] == 0.95
        assert memories[0]["provenance"]["human_verified"] is True

        # 2. Automated-only execution -> baseline signal (0.70 confidence)
        await memory.learn_from_execution(
            project_id=pid,
            execution_id=eid_auto,
            domain="auto-target.com",
            url="https://auto-target.com/page",
            human_verified=False,
        )
        memories_auto = await memory.store.query(pid, scope_key="auto-target.com")
        assert len(memories_auto) >= 1
        assert memories_auto[0]["confidence"] == 0.70
        assert memories_auto[0]["provenance"]["human_verified"] is False

        # 3. Human rejection -> negative signal in failure memory (confidence 0.20), not strengthening workflow
        await memory.learn_from_execution(
            project_id=pid,
            execution_id=eid_reject,
            domain="rejected-target.com",
            url="https://rejected-target.com/page",
            human_rejected=True,
            human_reason="Wrong form submitted",
        )
        memories_fail = await memory.store.query(pid, scope_key="rejected-target.com")
        assert len(memories_fail) >= 1
        assert memories_fail[0]["memory_type"] == MemoryType.FAILURE
        assert memories_fail[0]["confidence"] == 0.2
        assert memories_fail[0]["content"]["human_rejected"] is True

    @pytest.mark.asyncio
    async def test_f_audit_log(self, env):
        """Test F: Append-only audit logger records human verification decision with metadata."""
        config, db, registry, orch = env
        audit = orch.audit_logger
        eid = uuid4()

        # Log confirmation
        audit.log_human_verification(
            execution_id=eid,
            status="CONFIRMED",
            verified_by="security_auditor",
            automated_verification="PASS",
        )

        entries = audit.get_entries(eid)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.event_type == "human_verification"
        assert entry.execution_id == eid
        assert entry.actor == "security_auditor"
        assert entry.decision == "CONFIRMED"
        assert entry.details["automated_verification"] == "PASS"

        # Log rejection on different execution
        eid_rej = uuid4()
        audit.log_human_verification(
            execution_id=eid_rej,
            status="REJECTED",
            verified_by="compliance_officer",
            reason="PII leak risk",
            automated_verification="PASS",
        )
        entries_rej = audit.get_entries(eid_rej)
        assert len(entries_rej) == 1
        assert entries_rej[0].decision == "REJECTED"
        assert entries_rej[0].reason == "PII leak risk"
