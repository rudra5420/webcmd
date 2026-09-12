"""Mock worker for testing the WebCMD runtime.

Simulates various execution outcomes without requiring
real browser, API, or filesystem access.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from webcmd.workers.base import (
    BaseWorker,
    PermanentError,
    TransientError,
)
from webcmd.workers.types import (
    Capability,
    CapabilitySet,
    IdempotencyType,
    ObservationRecord,
    PauseResult,
    PreparedAction,
    ResumeResult,
    RiskLevel,
    SideEffectStatus,
    TrustLevel,
    WorkerContext,
    WorkerResult,
)


class MockWorker(BaseWorker):
    """Mock worker for testing.
    
    Configurable to simulate different outcomes:
    - success (default)
    - transient_failure (raises TransientError)
    - permanent_failure (raises PermanentError)
    - uncertain (returns status='uncertain')
    - slow (adds configurable delay)
    """
    
    def __init__(
        self,
        *,
        mode: str = "success",
        delay_s: float = 0.0,
        custom_observations: list[ObservationRecord] | None = None,
        custom_outputs: dict[str, Any] | None = None,
    ) -> None:
        self.mode = mode
        self.delay_s = delay_s
        self.custom_observations = custom_observations or []
        self.custom_outputs = custom_outputs or {}
        self._initialized = False
        self._paused = False
        self._execution_count = 0
    
    @property
    def worker_type(self) -> str:
        return "mock"
    
    @property
    def worker_name(self) -> str:
        return "Mock Worker"
    
    async def initialize(self, context: WorkerContext) -> None:
        self._initialized = True
    
    async def capabilities(self) -> CapabilitySet:
        return CapabilitySet(capabilities=[
            Capability(
                name="mock.execute",
                description="Mock execution for testing",
                idempotency=IdempotencyType.IDEMPOTENT,
                risk_level=RiskLevel.LOW,
            ),
            Capability(
                name="mock.side_effect",
                description="Mock side-effecting action",
                idempotency=IdempotencyType.NON_IDEMPOTENT,
                risk_level=RiskLevel.MEDIUM,
            ),
            Capability(
                name="browser.navigate",
                description="Mock browser navigation",
                idempotency=IdempotencyType.IDEMPOTENT,
                risk_level=RiskLevel.LOW,
            ),
            Capability(
                name="browser.click",
                description="Mock browser click",
                idempotency=IdempotencyType.CONDITIONALLY_IDEMPOTENT,
                risk_level=RiskLevel.LOW,
            ),
            Capability(
                name="filesystem.read",
                description="Mock file read",
                idempotency=IdempotencyType.IDEMPOTENT,
                risk_level=RiskLevel.LOW,
            ),
            Capability(
                name="filesystem.write",
                description="Mock file write",
                idempotency=IdempotencyType.NON_IDEMPOTENT,
                risk_level=RiskLevel.MEDIUM,
            ),
        ])
    
    async def prepare(
        self, action: PreparedAction, context: WorkerContext
    ) -> PreparedAction:
        if not self._initialized:
            raise PermanentError("Worker not initialized")
        return action
    
    async def execute(
        self, action: PreparedAction, context: WorkerContext
    ) -> WorkerResult:
        if not self._initialized:
            raise PermanentError("Worker not initialized")
        
        self._execution_count += 1
        
        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)
        
        now = datetime.now(timezone.utc)
        
        if self.mode == "transient_failure":
            raise TransientError("Simulated transient failure")
        
        if self.mode == "permanent_failure":
            raise PermanentError("Simulated permanent failure")
        
        if self.mode == "uncertain":
            return WorkerResult(
                status="uncertain",
                outputs=self.custom_outputs,
                observations=[
                    ObservationRecord(
                        observation_type="mock_uncertain",
                        data={"message": "Action outcome unknown"},
                        captured_at=now,
                        trust_class=TrustLevel.T4_TOOL_OUTPUT,
                    )
                ],
                side_effect_status=SideEffectStatus.UNKNOWN,
                duration_ms=self.delay_s * 1000,
            )
        
        # Success mode (default)
        default_observations = [
            ObservationRecord(
                observation_type="mock_success",
                data={
                    "action": action.capability,
                    "target": action.target,
                    "result": "completed",
                },
                captured_at=now,
                trust_class=TrustLevel.T4_TOOL_OUTPUT,
            )
        ]
        
        return WorkerResult(
            status="succeeded",
            outputs=self.custom_outputs or {"result": "mock_success"},
            observations=self.custom_observations or default_observations,
            side_effect_status=SideEffectStatus.NONE,
            duration_ms=self.delay_s * 1000,
        )
    
    async def observe(self, context: WorkerContext) -> list[ObservationRecord]:
        return [
            ObservationRecord(
                observation_type="mock_state",
                data={"initialized": self._initialized, "paused": self._paused, "executions": self._execution_count},
                captured_at=datetime.now(timezone.utc),
            )
        ]
    
    async def pause(self) -> PauseResult:
        self._paused = True
        return PauseResult(success=True, state_snapshot={"execution_count": self._execution_count})
    
    async def resume(self, context: WorkerContext) -> ResumeResult:
        self._paused = False
        return ResumeResult(success=True, message="Resumed successfully")
    
    async def cancel(self, reason: str) -> None:
        self._paused = False
    
    async def shutdown(self) -> None:
        self._initialized = False
        self._paused = False
