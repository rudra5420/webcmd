"""Tests for the WebCMD Web Interface and API."""
import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient

from webcmd.config import WebCMDConfig
from webcmd.core.orchestrator import Orchestrator
from webcmd.state.enums import ExecutionStatus
from webcmd.storage.database import DatabaseManager
from webcmd.web.server import create_app
from webcmd.workers.mock import MockWorker
from webcmd.workers.registry import WorkerRegistry


@pytest.fixture
async def web_env(tmp_path: Path):
    """Fixture providing initialized config, db, orchestrator, and test app."""
    config = WebCMDConfig(home_dir=tmp_path / ".webcmd")
    config.ensure_dirs()

    db = DatabaseManager(config.get_db_path())
    await db.initialize()

    registry = WorkerRegistry()
    registry.register(MockWorker)

    orch = Orchestrator(config, db, registry)
    app = create_app(config, orchestrator=orch)

    yield config, orch, app
    await db.close()


class TestWebServer:
    @pytest.mark.asyncio
    async def test_dashboard_loads(self, web_env):
        """Test GET / returns 200 and loads HTML dashboard."""
        _, _, app = web_env
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "WebCMD" in resp.text
            assert "CANONICAL EXECUTION TIMELINE" in resp.text
            assert "FINAL VERIFICATION REQUIRED" in resp.text

    @pytest.mark.asyncio
    async def test_api_health(self, web_env):
        """Test GET /api/health."""
        _, _, app = web_env
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "version" in data

    @pytest.mark.asyncio
    async def test_task_submission_and_execution_state(self, web_env):
        """Test task submission via POST /api/executions and retrieval via GET /api/executions/{id}."""
        _, orch, app = web_env
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Submit task
            resp = await client.post("/api/executions", json={"task": "Download monthly audit", "auto_confirm": False})
            assert resp.status_code == 200
            data = resp.json()
            assert "execution_id" in data
            eid = data["execution_id"]
            assert data["status"] == "pending"

            # Allow background execution to progress through automated verification to the human gate
            for _ in range(20):
                await asyncio.sleep(0.05)
                status_resp = await client.get(f"/api/executions/{eid}")
                if status_resp.status_code == 200:
                    ex_data = status_resp.json()["execution"]
                    if ex_data["status"] == ExecutionStatus.AWAITING_HUMAN_VERIFICATION:
                        break

            # 2. Check execution state at human gate
            detail_resp = await client.get(f"/api/executions/{eid}")
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            ex = detail["execution"]
            assert ex["status"] == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
            assert detail["human_verification"]["status"] == "pending"
            assert detail["human_verification"]["required"] is True

            # 3. Check checkpoint status
            assert len(detail["checkpoints"]) >= 1
            assert detail["checkpoints"][-1]["trigger"] == "pre_human_verification"

    @pytest.mark.asyncio
    async def test_human_confirmation_completes_execution(self, web_env):
        """Test confirming at human gate transitions state to COMPLETED and boosts memory confidence."""
        _, orch, app = web_env
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Run task until awaiting human verification
            execution = await orch.execute_task("Generate quarterly tax statement")
            assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
            eid = str(execution.execution_id)

            # Confirm execution via Web API
            confirm_resp = await client.post(
                f"/api/executions/{eid}/confirm",
                json={"verified_by": "qa_operator"},
            )
            assert confirm_resp.status_code == 200
            result_data = confirm_resp.json()
            assert result_data["status"] == "success"
            assert result_data["execution"]["status"] == ExecutionStatus.COMPLETED
            assert result_data["execution"]["human_verification"]["status"] == "confirmed"
            assert result_data["execution"]["human_verification"]["verified_by"] == "qa_operator"

    @pytest.mark.asyncio
    async def test_human_rejection_triggers_recovery(self, web_env):
        """Test rejecting at human gate transitions state to RECOVERING with failure code."""
        _, orch, app = web_env
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            execution = await orch.execute_task("Scrape vendor invoices")
            assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
            eid = str(execution.execution_id)

            # Reject execution via Web API
            reject_resp = await client.post(
                f"/api/executions/{eid}/reject",
                json={"reason": "Missing currency code column", "verified_by": "supervisor_jane"},
            )
            assert reject_resp.status_code == 200
            result_data = reject_resp.json()
            assert result_data["status"] == "rejected"
            assert result_data["execution"]["status"] == ExecutionStatus.RECOVERING
            assert "HUMAN_REJECTED" in result_data["execution"]["failure_code"]
            assert result_data["execution"]["human_verification"]["status"] == "rejected"
            assert "Missing currency code column" in result_data["execution"]["human_verification"]["reason"]

    @pytest.mark.asyncio
    async def test_memory_and_security_endpoints(self, web_env):
        """Test GET /api/memory and GET /api/security."""
        _, orch, app = web_env
        pid = uuid4()
        # Seed experiential memory
        await orch.memory_engine.remember_site(pid, "finance.portal", {"login_route": "/auth"})
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Memory endpoint
            mem_resp = await client.get("/api/memory")
            assert mem_resp.status_code == 200
            memories = mem_resp.json()
            assert len(memories) >= 1
            assert any(m["scope_key"] == "finance.portal" for m in memories)

            # Security endpoint
            sec_resp = await client.get("/api/security")
            assert sec_resp.status_code == 200
            sec_data = sec_resp.json()
            assert sec_data["policy"] == "ACTIVE"
            assert "Never displayed" in sec_data["raw_secrets"]

    @pytest.mark.asyncio
    async def test_cancel_execution_endpoint(self, web_env):
        """Test POST /api/executions/{id}/cancel."""
        _, orch, app = web_env
        execution = await orch.execute_task("Long running task")
        eid = str(execution.execution_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/executions/{eid}/cancel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "cancelled"

    def test_websocket_event_streaming(self, web_env):
        """Test WebSocket event streaming for execution events."""
        _, orch, app = web_env
        client = TestClient(app)
        eid = uuid4()

        with client.websocket_connect(f"/ws/executions/{eid}") as websocket:
            # Send ping
            websocket.send_json({"type": "ping"})
            resp = websocket.receive_json()
            assert resp.get("type") == "pong"

    @pytest.mark.asyncio
    async def test_page_survives_execution_restart(self, web_env):
        """Test that execution state and dashboard survive server restart across the human gate."""
        config, orch, app = web_env
        execution = await orch.execute_task("Batch extraction across restart")
        assert execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
        eid = str(execution.execution_id)

        # Emulate server process restart with same config and underlying database
        new_orch = Orchestrator(config, orch.db, orch.worker_registry)
        restarted_app = create_app(config, orchestrator=new_orch)

        transport = ASGITransport(app=restarted_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Dashboard loads on restarted server
            dash_resp = await client.get("/")
            assert dash_resp.status_code == 200

            # Execution state is preserved
            detail_resp = await client.get(f"/api/executions/{eid}")
            assert detail_resp.status_code == 200
            data = detail_resp.json()
            assert data["execution"]["status"] == ExecutionStatus.AWAITING_HUMAN_VERIFICATION
            assert data["human_verification"]["status"] == "pending"
            assert len(data["checkpoints"]) >= 1

            # Human confirmation succeeds on restarted instance
            confirm_resp = await client.post(
                f"/api/executions/{eid}/confirm",
                json={"verified_by": "recovery_admin"},
            )
            assert confirm_resp.status_code == 200
            assert confirm_resp.json()["execution"]["status"] == ExecutionStatus.COMPLETED

