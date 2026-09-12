"""Unit tests for WebCMD worker contract."""
import pytest
from uuid import uuid4

from webcmd.workers.base import BaseWorker, TransientError, PermanentError
from webcmd.workers.mock import MockWorker
from webcmd.workers.types import (
    CapabilitySet,
    PreparedAction,
    WorkerContext,
    WorkerResult,
)
from webcmd.workers.registry import WorkerRegistry


def make_context() -> WorkerContext:
    return WorkerContext(
        execution_id=uuid4(),
        step_id=uuid4(),
        worker_run_id=uuid4(),
    )


def make_action(capability: str = "mock.execute") -> PreparedAction:
    return PreparedAction(
        worker_type="mock",
        capability=capability,
        target="test_target",
    )


class TestMockWorker:
    async def test_success_mode(self):
        worker = MockWorker(mode="success")
        ctx = make_context()
        await worker.initialize(ctx)
        action = make_action()
        result = await worker.execute(action, ctx)
        assert result.status == "succeeded"
        assert len(result.observations) > 0
    
    async def test_transient_failure(self):
        worker = MockWorker(mode="transient_failure")
        ctx = make_context()
        await worker.initialize(ctx)
        with pytest.raises(TransientError):
            await worker.execute(make_action(), ctx)
    
    async def test_permanent_failure(self):
        worker = MockWorker(mode="permanent_failure")
        ctx = make_context()
        await worker.initialize(ctx)
        with pytest.raises(PermanentError):
            await worker.execute(make_action(), ctx)
    
    async def test_uncertain_mode(self):
        worker = MockWorker(mode="uncertain")
        ctx = make_context()
        await worker.initialize(ctx)
        result = await worker.execute(make_action(), ctx)
        assert result.status == "uncertain"
        assert result.side_effect_status == "unknown"
    
    async def test_capabilities(self):
        worker = MockWorker()
        caps = await worker.capabilities()
        assert isinstance(caps, CapabilitySet)
        assert caps.has("mock.execute")
        assert caps.has("browser.navigate")
        assert not caps.has("nonexistent")
    
    async def test_pause_resume(self):
        worker = MockWorker()
        ctx = make_context()
        await worker.initialize(ctx)
        pause_result = await worker.pause()
        assert pause_result.success
        resume_result = await worker.resume(ctx)
        assert resume_result.success
    
    async def test_observe(self):
        worker = MockWorker()
        ctx = make_context()
        await worker.initialize(ctx)
        observations = await worker.observe(ctx)
        assert len(observations) > 0
    
    async def test_lifecycle(self):
        worker = MockWorker()
        ctx = make_context()
        await worker.initialize(ctx)
        action = make_action()
        prepared = await worker.prepare(action, ctx)
        result = await worker.execute(prepared, ctx)
        assert result.status == "succeeded"
        await worker.shutdown()


class TestWorkerRegistry:
    async def test_register_and_get(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        worker = await registry.get_worker("mock")
        assert isinstance(worker, MockWorker)
    
    async def test_capabilities_caching(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        caps = await registry.get_capabilities("mock")
        assert caps.has("mock.execute")
    
    async def test_find_workers_for_capability(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        await registry.get_capabilities("mock")
        workers = registry.find_workers_for_capability("browser.navigate")
        assert "mock" in workers
    
    async def test_find_best_worker(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        best = await registry.find_best_worker(["mock.execute"])
        assert best == "mock"
    
    async def test_find_best_worker_no_match(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        best = await registry.find_best_worker(["nonexistent.capability"])
        assert best is None
    
    async def test_shutdown_all(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        await registry.get_worker("mock")
        await registry.shutdown_all()
        assert len(registry._worker_instances) == 0
