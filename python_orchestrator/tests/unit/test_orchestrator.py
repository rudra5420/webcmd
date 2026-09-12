"""Tests for the WebCMD orchestrator."""
import pytest
from pathlib import Path

from webcmd.config import WebCMDConfig
from webcmd.core.orchestrator import Orchestrator
from webcmd.state.enums import ExecutionStatus
from webcmd.storage.database import DatabaseManager
from webcmd.workers.mock import MockWorker
from webcmd.workers.registry import WorkerRegistry


@pytest.fixture
async def orchestrator(tmp_path: Path):
    config = WebCMDConfig(home_dir=tmp_path / ".webcmd")
    config.ensure_dirs()
    
    db = DatabaseManager(config.get_db_path())
    await db.initialize()
    
    registry = WorkerRegistry()
    registry.register(MockWorker)
    
    orch = Orchestrator(config, db, registry)
    yield orch
    await db.close()


class TestOrchestrator:
    async def test_execute_task_requires_human_verification(self, orchestrator):
        execution = await orchestrator.execute_task("test task")
        assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
        assert execution.result is not None
        assert execution.human_verification is not None
        assert execution.human_verification.required is True
        
        # Human confirms
        confirmed = await orchestrator.confirm_execution(execution.execution_id, verified_by="operator")
        assert confirmed.status == ExecutionStatus.COMPLETED
        assert confirmed.human_verification.status == "confirmed"

    async def test_execute_task_auto_confirm(self, orchestrator):
        execution = await orchestrator.execute_task("test task", auto_confirm=True)
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.human_verification.status == "confirmed"
    
    async def test_execute_task_creates_events(self, orchestrator):
        execution = await orchestrator.execute_task("test task")
        events = await orchestrator.event_store.get_events(execution.execution_id)
        assert len(events) >= 3  # created, started, verification requested
        types = [e.event_type for e in events]
        assert "HumanVerificationRequested" in types
    
    async def test_get_execution(self, orchestrator):
        execution = await orchestrator.execute_task("test task")
        retrieved = await orchestrator.get_execution(execution.execution_id)
        assert retrieved is not None
        assert retrieved.execution_id == execution.execution_id
    
    async def test_list_executions(self, orchestrator):
        await orchestrator.execute_task("task 1")
        await orchestrator.execute_task("task 2")
        executions = await orchestrator.list_executions()
        assert len(executions) >= 2
