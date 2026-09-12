"""Tests for WebCMD handoff protocol."""
import pytest
from uuid import uuid4

from webcmd.handoff.envelope import HandoffEnvelope
from webcmd.handoff.session_bridge import SessionBridge
from webcmd.handoff.manager import HandoffManager
from webcmd.state.enums import HandoffStatus, HandoffReason
from webcmd.workers.mock import MockWorker
from webcmd.workers.registry import WorkerRegistry


class TestSessionBridge:
    def test_create_and_resolve(self):
        bridge = SessionBridge()
        ref = bridge.create_session_ref({"cookie": "abc123", "token": "xyz"})
        data = bridge.resolve_session_ref(ref)
        assert data is not None
        assert data["cookie"] == "abc123"
    
    def test_revoke(self):
        bridge = SessionBridge()
        ref = bridge.create_session_ref({"secret": "value"})
        bridge.revoke_session_ref(ref)
        assert bridge.resolve_session_ref(ref) is None


class TestHandoffManager:
    async def test_full_lifecycle(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        await registry.get_capabilities("mock")
        
        manager = HandoffManager(registry)
        
        envelope = await manager.initiate_handoff(
            execution_id=uuid4(),
            source_worker_run_id=uuid4(),
            target_worker_type="mock",
            reason=HandoffReason.CAPABILITY_CHANGE,
            context_data={"url": "https://example.com"},
            required_capabilities=["mock.execute"],
        )
        assert envelope.status == HandoffStatus.REQUESTED
        
        valid, msg = await manager.validate_handoff(envelope.handoff_id)
        assert valid
        
        accepted = await manager.accept_handoff(envelope.handoff_id)
        assert accepted.status == HandoffStatus.ACCEPTED
        
        completed = await manager.complete_handoff(envelope.handoff_id)
        assert completed.status == HandoffStatus.COMPLETED
    
    async def test_missing_capability_rejected(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        await registry.get_capabilities("mock")
        
        manager = HandoffManager(registry)
        envelope = await manager.initiate_handoff(
            execution_id=uuid4(),
            source_worker_run_id=uuid4(),
            target_worker_type="mock",
            reason=HandoffReason.CAPABILITY_CHANGE,
            required_capabilities=["nonexistent.cap"],
        )
        valid, msg = await manager.validate_handoff(envelope.handoff_id)
        assert not valid
    
    async def test_session_bridge_in_handoff(self):
        registry = WorkerRegistry()
        registry.register(MockWorker)
        await registry.get_capabilities("mock")
        
        manager = HandoffManager(registry)
        envelope = await manager.initiate_handoff(
            execution_id=uuid4(),
            source_worker_run_id=uuid4(),
            target_worker_type="mock",
            reason=HandoffReason.CAPABILITY_CHANGE,
            session_data={"auth_cookie": "secret_value"},
        )
        assert envelope.session_ref is not None
        
        # Session data accessible via bridge
        data = manager.session_bridge.resolve_session_ref(envelope.session_ref)
        assert data["auth_cookie"] == "secret_value"
        
        # After completion, session revoked
        await manager.complete_handoff(envelope.handoff_id)
        assert manager.session_bridge.resolve_session_ref(envelope.session_ref) is None
