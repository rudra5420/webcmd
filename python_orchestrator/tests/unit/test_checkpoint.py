"""Tests for WebCMD checkpoint system."""
import pytest
from pathlib import Path
from uuid import uuid4

from webcmd.checkpoint.hasher import CanonicalHasher
from webcmd.checkpoint.manager import CheckpointManager
from webcmd.checkpoint.models import (
    CheckpointData,
    CheckpointTrigger,
    LogicalCheckpoint,
    EnvironmentalCheckpoint,
    ResumeBoundary,
)
from webcmd.checkpoint.resumer import ResumeCoordinator, ResumeDecision
from webcmd.config import WebCMDConfig


@pytest.fixture
def checkpoint_manager(tmp_path: Path) -> CheckpointManager:
    config = WebCMDConfig(home_dir=tmp_path / ".webcmd")
    config.ensure_dirs()
    return CheckpointManager(config)


class TestCanonicalHasher:
    def test_deterministic(self):
        data = {"b": 2, "a": 1}
        h1 = CanonicalHasher.compute_hash(data)
        h2 = CanonicalHasher.compute_hash(data)
        assert h1 == h2
    
    def test_different_data_different_hash(self):
        h1 = CanonicalHasher.compute_hash({"a": 1})
        h2 = CanonicalHasher.compute_hash({"a": 2})
        assert h1 != h2
    
    def test_verify_hash(self):
        data = {"key": "value"}
        h = CanonicalHasher.compute_hash(data)
        assert CanonicalHasher.verify_hash(data, h)
        assert not CanonicalHasher.verify_hash({"key": "other"}, h)
    
    def test_key_order_independent(self):
        h1 = CanonicalHasher.compute_hash({"z": 1, "a": 2})
        h2 = CanonicalHasher.compute_hash({"a": 2, "z": 1})
        assert h1 == h2


class TestCheckpointManager:
    async def test_create_checkpoint(self, checkpoint_manager):
        eid = uuid4()
        cp = await checkpoint_manager.create(
            execution_id=eid,
            trigger=CheckpointTrigger.POST_STEP,
        )
        assert cp.execution_id == eid
        assert cp.state_hash is not None
    
    async def test_get_latest(self, checkpoint_manager):
        eid = uuid4()
        await checkpoint_manager.create(eid, CheckpointTrigger.POST_STEP)
        cp2 = await checkpoint_manager.create(eid, CheckpointTrigger.POST_STEP)
        
        latest = await checkpoint_manager.get_latest(eid)
        assert latest is not None
        assert latest.sequence_number == cp2.sequence_number
    
    async def test_integrity_verification(self, checkpoint_manager):
        eid = uuid4()
        cp = await checkpoint_manager.create(
            execution_id=eid,
            trigger=CheckpointTrigger.POST_STEP,
            logical=LogicalCheckpoint(
                completed_steps=[uuid4()],
                variable_bindings={"key": "value"},
            ),
        )
        
        # Reload and verify
        loaded = await checkpoint_manager.get_latest(eid)
        assert loaded is not None
        assert loaded.state_hash == cp.state_hash
    
    async def test_get_all(self, checkpoint_manager):
        eid = uuid4()
        for _ in range(5):
            await checkpoint_manager.create(eid, CheckpointTrigger.POST_STEP)
        
        all_cps = await checkpoint_manager.get_all(eid)
        assert len(all_cps) == 5
    
    async def test_prune(self, checkpoint_manager):
        eid = uuid4()
        for _ in range(10):
            await checkpoint_manager.create(eid, CheckpointTrigger.POST_STEP)
        await checkpoint_manager.create(eid, CheckpointTrigger.PRE_RISK)
        
        pruned = await checkpoint_manager.prune(eid, keep_last_n=3)
        assert pruned > 0
        
        remaining = await checkpoint_manager.get_all(eid)
        assert len(remaining) <= 4  # 3 latest + 1 pre_risk


class TestResumeCoordinator:
    async def test_no_checkpoint_no_resume(self, checkpoint_manager):
        coordinator = ResumeCoordinator(checkpoint_manager)
        decision = await coordinator.evaluate_resume(uuid4())
        assert not decision.can_resume
    
    async def test_resume_with_checkpoint(self, checkpoint_manager):
        eid = uuid4()
        next_step = uuid4()
        await checkpoint_manager.create(
            execution_id=eid,
            trigger=CheckpointTrigger.POST_STEP,
            logical=LogicalCheckpoint(
                completed_steps=[uuid4()],
                pending_steps=[next_step],
            ),
            resume_boundary=ResumeBoundary(
                last_verified_step_id=uuid4(),
                next_step_id=next_step,
            ),
        )
        
        coordinator = ResumeCoordinator(checkpoint_manager)
        decision = await coordinator.evaluate_resume(eid)
        assert decision.can_resume
        assert decision.resume_from_step_id == next_step
    
    async def test_uncertain_effects_block_unprobed_resume(self, checkpoint_manager):
        eid = uuid4()
        await checkpoint_manager.create(
            execution_id=eid,
            trigger=CheckpointTrigger.PRE_RISK,
            logical=LogicalCheckpoint(pending_steps=[uuid4()]),
            resume_boundary=ResumeBoundary(
                next_step_id=uuid4(),
                uncertain_side_effects=[{"action": "purchase", "status": "unknown"}],
            ),
        )
        
        coordinator = ResumeCoordinator(checkpoint_manager)
        decision = await coordinator.evaluate_resume(eid)
        
        confirmed = await coordinator.confirm_resume(decision, environment_probed=False)
        assert not confirmed
        
        confirmed = await coordinator.confirm_resume(decision, environment_probed=True)
        assert confirmed
