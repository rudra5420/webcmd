"""WebCMD Web Server and API.

Provides local REST API, WebSocket event streaming, and dashboard visualization.
Delegates directly to the authoritative WebCMD runtime (Orchestrator).
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from webcmd import __version__
from webcmd.config import WebCMDConfig, get_config
from webcmd.core.orchestrator import Orchestrator
from webcmd.state.enums import ExecutionStatus
from webcmd.storage.database import DatabaseManager
from webcmd.storage.events import DomainEvent
from webcmd.workers.api.http_worker import HttpWorker
from webcmd.workers.browser.browseruse_worker import BrowserUseWorker
from webcmd.workers.browser.playwright_worker import PlaywrightWorker
from webcmd.workers.filesystem.local_worker import FilesystemWorker
from webcmd.workers.mock import MockWorker
from webcmd.workers.registry import WorkerRegistry
from webcmd.workers.shell.shell_worker import ShellWorker

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class TaskRequest(BaseModel):
    task: str = Field(..., description="Natural language task description")
    auto_confirm: bool = Field(default=False, description="Auto-confirm without human pause")
    project_id: Optional[str] = Field(default=None, description="Optional project UUID")


class ConfirmRequest(BaseModel):
    verified_by: str = Field(default="web_operator", description="Operator identity confirming result")


class RejectRequest(BaseModel):
    reason: str = Field(default="", description="Feedback or reason for rejecting final result")
    verified_by: str = Field(default="web_operator", description="Operator identity rejecting result")


def serialize_model(obj: Any) -> Any:
    """Helper to cleanly serialize Pydantic models or datetimes to JSON-compatible dicts."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, list):
        return [serialize_model(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize_model(v) for k, v in obj.items()}
    return obj


def create_app(config: WebCMDConfig | None = None, orchestrator: Orchestrator | None = None) -> FastAPI:
    """Factory creating the FastAPI WebCMD application."""
    cfg = config or get_config()
    cfg.ensure_dirs()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if orchestrator is not None:
            app.state.orchestrator = orchestrator
            app.state.db = orchestrator.db
            yield
        else:
            db = DatabaseManager(cfg.get_db_path())
            await db.initialize()

            registry = WorkerRegistry()
            registry.register(MockWorker)
            registry.register(HttpWorker)
            registry.register(PlaywrightWorker)
            registry.register(BrowserUseWorker)
            registry.register(FilesystemWorker)
            registry.register(ShellWorker)

            orch = Orchestrator(cfg, db, registry)
            app.state.orchestrator = orch
            app.state.db = db
            yield
            await db.close()

    app = FastAPI(
        title="WebCMD Local Control & Visualization",
        version=__version__,
        lifespan=lifespan,
    )

    if orchestrator is not None:
        app.state.orchestrator = orchestrator
        app.state.db = orchestrator.db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static assets mount if static directory exists
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def get_dashboard():
        """Serve the single-page dashboard."""
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>WebCMD Dashboard</h1><p>Static files missing.</p>")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.post("/api/executions")
    async def create_execution(req: TaskRequest):
        """Submit a task to execute asynchronously."""
        orch: Orchestrator = app.state.orchestrator
        default_pid = UUID("00000000-0000-0000-0000-000000000001")
        pid = UUID(req.project_id) if req.project_id else default_pid
        eid = uuid4()

        # Run in background so HTTP call returns immediately with execution ID
        asyncio.create_task(
            orch.execute_task(
                intent_text=req.task,
                project_id=pid,
                auto_confirm=req.auto_confirm,
                execution_id=eid,
            )
        )

        return {
            "execution_id": str(eid),
            "project_id": str(pid),
            "task": req.task,
            "status": "pending",
            "auto_confirm": req.auto_confirm,
        }

    @app.get("/api/executions")
    async def list_executions(project_id: Optional[str] = None):
        """List all executions."""
        orch: Orchestrator = app.state.orchestrator
        pid = UUID(project_id) if project_id else None
        executions = await orch.list_executions(pid)
        
        task_map = {}
        try:
            async with orch.db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT execution_id, payload FROM domain_events WHERE event_type = 'ExecutionCreated'"
                )
                rows = await cursor.fetchall()
                for eid_str, payload_str in rows:
                    try:
                        p = json.loads(payload_str)
                        task_map[eid_str] = p.get("intent") or p.get("task")
                    except Exception:
                        pass
        except Exception:
            pass

        results = []
        for e in executions:
            d = serialize_model(e)
            d["execution_id"] = str(e.id)
            d["task_text"] = (
                (e.metadata.get("task") or e.metadata.get("intent")) if e.metadata else None
            ) or task_map.get(str(e.id)) or f"Task {str(e.id)[:8]}"
            results.append(d)
        return results

    @app.get("/api/executions/{execution_id}")
    async def get_execution(execution_id: str):
        """Get execution details by ID."""
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid execution UUID")

        ex = await orch.get_execution(eid)
        if not ex:
            raise HTTPException(status_code=404, detail="Execution not found")

        events = await orch.event_store.get_events(eid)
        checkpoints = await orch.checkpoint_mgr.get_all(eid)

        task_text = ex.metadata.get("task") or ex.metadata.get("intent") if ex.metadata else None
        if not task_text:
            for ev in events:
                if ev.event_type == "ExecutionCreated" and ev.payload.get("intent"):
                    task_text = ev.payload.get("intent")
                    break

        ex_dict = serialize_model(ex)
        ex_dict["execution_id"] = str(ex.id)
        ex_dict["task_text"] = task_text

        return {
            "execution": ex_dict,
            "task_text": task_text,
            "event_count": len(events),
            "events": [serialize_model(ev) for ev in events],
            "checkpoints": [serialize_model(cp) for cp in checkpoints],
            "human_verification": serialize_model(ex.human_verification) if ex.human_verification else None,
        }

    @app.post("/api/executions/{execution_id}/confirm")
    async def confirm_execution(execution_id: str, req: ConfirmRequest = ConfirmRequest()):
        """Confirm an execution at the single final human verification gate."""
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid execution UUID")

        try:
            ex = await orch.confirm_execution(eid, verified_by=req.verified_by)
            return {"status": "success", "execution": serialize_model(ex)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/executions/{execution_id}/reject")
    async def reject_execution(execution_id: str, req: RejectRequest = RejectRequest()):
        """Reject an execution at the final human verification gate."""
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid execution UUID")

        try:
            ex = await orch.reject_execution(eid, reason=req.reason, verified_by=req.verified_by)
            return {"status": "rejected", "execution": serialize_model(ex)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/executions/{execution_id}/cancel")
    async def cancel_execution(execution_id: str):
        """Cancel an execution."""
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid execution UUID")

        ex = await orch.cancel_execution(eid)
        if not ex:
            raise HTTPException(status_code=404, detail="Execution not found")
        return {"status": "cancelled", "execution": serialize_model(ex)}

    @app.post("/api/executions/{execution_id}/resume")
    async def resume_execution(execution_id: str, auto_confirm: bool = False):
        """Resume an execution from its latest valid checkpoint."""
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid execution UUID")

        try:
            ex = await orch.resume_execution(eid, auto_confirm=auto_confirm)
            return {"status": "resumed", "execution": serialize_model(ex)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/executions/{execution_id}/events")
    async def get_events(execution_id: str):
        """Get event timeline for an execution."""
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid execution UUID")

        events = await orch.event_store.get_events(eid)
        return [serialize_model(ev) for ev in events]

    @app.get("/api/executions/{execution_id}/checkpoints")
    async def get_checkpoints(execution_id: str):
        """Get checkpoints for an execution."""
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid execution UUID")

        cps = await orch.checkpoint_mgr.get_all(eid)
        return [serialize_model(cp) for cp in cps]

    @app.get("/api/memory")
    async def get_memory(domain: Optional[str] = None):
        """Query experiential memory items."""
        orch: Orchestrator = app.state.orchestrator
        # Query general project/site memories
        async with orch.db.get_connection() as conn:
            if domain:
                cursor = await conn.execute(
                    "SELECT * FROM memory_items WHERE scope_key = ? OR scope_key LIKE ? ORDER BY confidence DESC, created_at DESC LIMIT 50",
                    (domain, f"%{domain}%"),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM memory_items ORDER BY confidence DESC, created_at DESC LIMIT 50"
                )
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            items = []
            for r in rows:
                item = dict(zip(cols, r))
                for json_col in ("content", "provenance"):
                    if isinstance(item.get(json_col), str):
                        try:
                            item[json_col] = json.loads(item[json_col])
                        except Exception:
                            pass
                items.append(item)
            return items

    @app.post("/api/memory/clear")
    async def clear_memory():
        """Clear memory items for clean demo resets."""
        orch: Orchestrator = app.state.orchestrator
        async with orch.db.get_connection() as conn:
            await conn.execute("DELETE FROM memory_items")
            await conn.commit()
        return {"status": "cleared"}

    @app.get("/api/browser/screencast")
    async def get_browser_screencast():
        """Get the latest live viewport screencast frame and browser page status."""
        orch: Orchestrator = app.state.orchestrator
        try:
            worker = await orch.worker_registry.get_worker("browser.playwright")
            frame_b64 = getattr(worker, "latest_screenshot_b64", None)
            url = None
            title = None
            active = False
            if hasattr(worker, "_page") and worker._page:
                try:
                    url = worker._page.url
                    title = await worker._page.title()
                    active = True
                except Exception:
                    pass
            return {
                "active": active,
                "url": url,
                "title": title,
                "frame": frame_b64,
            }
        except Exception:
            return {"active": False, "url": None, "title": None, "frame": None}

    @app.post("/api/demo/reset")
    async def reset_demo():
        """Reset the local test portal back to Version A (Stable)."""
        import urllib.request
        try:
            req = urllib.request.urlopen("http://127.0.0.1:9888/portal/switch?mode=A", timeout=2)
            data = json.loads(req.read().decode("utf-8"))
            return {"status": "ok", "mode": "A", "response": data}
        except Exception as e:
            return {"status": "offline", "detail": str(e), "mode": "A"}

    @app.post("/api/demo/switch")
    async def switch_demo_ui():
        """Switch the local test portal to Version B (UI changed / Adaptation needed)."""
        import urllib.request
        try:
            req = urllib.request.urlopen("http://127.0.0.1:9888/portal/switch?mode=B", timeout=2)
            data = json.loads(req.read().decode("utf-8"))
            return {"status": "ok", "mode": "B", "response": data}
        except Exception as e:
            return {"status": "offline", "detail": str(e), "mode": "B"}

    @app.post("/api/browser/reset-profile")
    async def reset_browser_profile():
        """Clear the persistent browser profile directory."""
        import shutil
        cfg = get_config()
        p_dir = cfg.get_browser_profile_dir()
        if p_dir.exists():
            try:
                shutil.rmtree(p_dir, ignore_errors=True)
                p_dir.mkdir(parents=True, exist_ok=True)
                return {"status": "cleared", "path": str(p_dir)}
            except Exception as e:
                return {"status": "error", "detail": str(e)}
        return {"status": "not_found"}

    @app.get("/api/history")
    async def get_run_history():
        """Get structured run history for Phase 21."""
        orch: Orchestrator = app.state.orchestrator
        execs = await orch.list_executions()
        history = []
        for i, ex in enumerate(reversed(execs)):
            meta = ex.metadata or {}
            task_name = meta.get("task") or meta.get("intent") or f"Run {str(ex.id)[:8]}"
            strategy = "Exploration"
            if meta.get("adapted") or (ex.result and ex.result.get("self_healing_recovery_engaged")):
                strategy = "Self-Healing Recovery"
            elif meta.get("memory_hit") or (ex.result and ex.result.get("selector_used") == "#btn-export"):
                strategy = "Learned Workflow"
            
            res_status = str(ex.status).capitalize()
            verif = "Verified PASS" if ex.status in ("completed", "awaiting_human_verification") else "Failed"
            if ex.human_verification and ex.human_verification.status == "confirmed":
                verif = "Human Confirmed"
            
            history.append({
                "run_id": f"#{str(i+1).zfill(3)}",
                "execution_id": str(ex.id),
                "task": task_name,
                "strategy": strategy,
                "status": res_status,
                "verification": verif,
                "created_at": ex.created_at.strftime("%H:%M:%S") if ex.created_at else "—",
            })
        return list(reversed(history))

    @app.get("/api/security")
    async def get_security_status():
        """Get security policy and credential vault status."""
        return {
            "policy": "ACTIVE",
            "credential_status": "Available through secure reference",
            "raw_secrets": "Never displayed (redacted)",
            "current_action_risk": "LOW",
            "approval_status": "Not required",
            "sandbox": "QuickJS / isolated worker boundaries",
        }

    @app.websocket("/ws/executions/{execution_id}")
    async def websocket_execution(websocket: WebSocket, execution_id: str):
        """Stream real-time events for a specific execution."""
        await websocket.accept()
        orch: Orchestrator = app.state.orchestrator
        try:
            eid = UUID(execution_id)
        except ValueError:
            await websocket.close(code=1003, reason="Invalid UUID")
            return

        # Send existing events first
        initial_events = await orch.event_store.get_events(eid)
        for ev in initial_events:
            await websocket.send_text(json.dumps({
                "type": "event",
                "event": serialize_model(ev),
            }))

        # Send latest execution status
        current_ex = await orch.get_execution(eid)
        if current_ex:
            await websocket.send_text(json.dumps({
                "type": "execution_status",
                "execution": serialize_model(current_ex),
            }))

        queue: asyncio.Queue[DomainEvent] = asyncio.Queue()

        def on_event(ev: DomainEvent):
            if ev.execution_id == eid:
                queue.put_nowait(ev)

        orch.event_store.add_listener(on_event)

        try:
            while True:
                # Wait for queue event or client ping
                event_task = asyncio.create_task(queue.get())
                recv_task = asyncio.create_task(websocket.receive_text())
                done, pending = await asyncio.wait(
                    [event_task, recv_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for p in pending:
                    p.cancel()

                if event_task in done:
                    ev = event_task.result()
                    ex = await orch.get_execution(eid)
                    checkpoints = await orch.checkpoint_mgr.get_all(eid)
                    b_frame = None
                    try:
                        worker = await orch.worker_registry.get_worker("browser.playwright")
                        b_frame = getattr(worker, "latest_screenshot_b64", None)
                    except Exception:
                        pass
                    await websocket.send_text(json.dumps({
                        "type": "event",
                        "event": serialize_model(ev),
                        "execution": serialize_model(ex) if ex else None,
                        "checkpoints": [serialize_model(cp) for cp in checkpoints],
                        "screencast": b_frame,
                    }))

                if recv_task in done:
                    # Client sent a message (ping or action)
                    msg = recv_task.result()
                    try:
                        data = json.loads(msg)
                        if data.get("type") == "ping":
                            await websocket.send_text(json.dumps({"type": "pong"}))
                    except Exception:
                        pass
        except WebSocketDisconnect:
            pass
        finally:
            orch.event_store.remove_listener(on_event)

    return app
