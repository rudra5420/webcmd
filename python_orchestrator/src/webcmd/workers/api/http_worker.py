import httpx
from datetime import datetime, timezone
import time
from typing import Any

from webcmd.workers.base import BaseWorker, WorkerError
from webcmd.workers.types import (
    Capability,
    CapabilitySet,
    PauseResult,
    PreparedAction,
    ResumeResult,
    WorkerContext,
    WorkerResult,
    ObservationRecord
)
from webcmd.state.enums import IdempotencyType, RiskLevel, SideEffectStatus, TrustLevel

class HttpWorker(BaseWorker):
    """
    HTTP Worker for making direct API calls.
    Capabilities: api.get, api.post, api.put, api.delete
    Uses httpx.AsyncClient.
    """
    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._context: WorkerContext | None = None
        self._paused_state: dict[str, Any] = {}

    @property
    def worker_type(self) -> str:
        return "api.http"

    @property
    def worker_name(self) -> str:
        return "HTTP Client Worker"

    async def initialize(self, context: WorkerContext) -> None:
        self._context = context
        self._client = httpx.AsyncClient()

    async def capabilities(self) -> CapabilitySet:
        return CapabilitySet(
            capabilities=[
                Capability(name="api.get", description="HTTP GET request", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
                Capability(name="api.post", description="HTTP POST request", idempotency=IdempotencyType.NON_IDEMPOTENT, risk_level=RiskLevel.MEDIUM),
                Capability(name="api.put", description="HTTP PUT request", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.MEDIUM),
                Capability(name="api.delete", description="HTTP DELETE request", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.HIGH),
            ]
        )

    async def prepare(self, action: PreparedAction, context: WorkerContext) -> PreparedAction:
        if action.capability not in ["api.get", "api.post", "api.put", "api.delete"]:
            raise WorkerError(f"Unsupported capability {action.capability}")
        return action

    async def execute(self, action: PreparedAction, context: WorkerContext) -> WorkerResult:
        if not self._client:
            raise WorkerError("Worker not initialized", retryable=True)

        method = action.capability.split(".")[1].upper()
        url = action.target or action.parameters.get("url")
        if not url:
            raise WorkerError("URL is required")

        headers = action.parameters.get("headers", {})
        json_data = action.parameters.get("json", None)
        params = action.parameters.get("params", None)

        start_time = time.time()
        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=context.time_budget_s
            )
            duration_ms = (time.time() - start_time) * 1000

            obs = ObservationRecord(
                observation_type="http_response",
                data={
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "duration_ms": duration_ms
                },
                trust_class=TrustLevel.T4_TOOL_OUTPUT
            )

            side_effect = SideEffectStatus.NONE if method == "GET" else SideEffectStatus.COMMITTED

            return WorkerResult(
                status="succeeded" if response.status_code < 400 else "failed",
                outputs={"status_code": response.status_code, "body": response.text},
                observations=[obs],
                side_effect_status=side_effect,
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return WorkerResult(
                status="failed",
                failure_message=str(e),
                retryable=True,
                duration_ms=duration_ms
            )

    async def observe(self, context: WorkerContext) -> list:
        # HTTP worker generally captures observations during execution
        return []

    async def pause(self) -> PauseResult:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._paused_state = {"paused_at": datetime.now(timezone.utc).isoformat()}
        return PauseResult(success=True, state_snapshot=self._paused_state)

    async def resume(self, context: WorkerContext) -> ResumeResult:
        self._client = httpx.AsyncClient()
        self._context = context
        return ResumeResult(success=True, message="Resumed HTTP worker")

    async def cancel(self, reason: str) -> None:
        if self._client:
            await self._client.aclose()

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
