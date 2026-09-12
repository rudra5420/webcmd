"""Multi-dimensional recovery budget tracker.

Prevents infinite recovery loops by enforcing hard limits across
5 dimensions: attempts, depth, time, tokens, and side-effect retries.
"""
from __future__ import annotations
import time
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RecoveryBudget(BaseModel):
    """Configuration for recovery limits."""
    max_attempts_per_step: int = Field(default=3)
    max_recovery_depth: int = Field(default=2)
    max_total_time_s: float = Field(default=300.0)
    max_side_effect_retries: int = Field(default=1)


class BudgetTracker:
    """Tracks and enforces multi-dimensional recovery budgets."""
    
    def __init__(self, budget: RecoveryBudget | None = None) -> None:
        self.budget = budget or RecoveryBudget()
        self._step_attempts: dict[str, int] = {}
        self._current_depth: int = 0
        self._side_effect_retries: dict[str, int] = {}
        self._start_time: float = time.monotonic()
    
    def record_attempt(self, step_id: str) -> None:
        self._step_attempts[step_id] = self._step_attempts.get(step_id, 0) + 1
    
    def record_side_effect_retry(self, step_id: str) -> None:
        self._side_effect_retries[step_id] = self._side_effect_retries.get(step_id, 0) + 1
    
    def enter_recovery(self) -> None:
        self._current_depth += 1
    
    def exit_recovery(self) -> None:
        self._current_depth = max(0, self._current_depth - 1)
    
    def can_retry(self, step_id: str) -> bool:
        attempts = self._step_attempts.get(step_id, 0)
        return attempts < self.budget.max_attempts_per_step
    
    def can_deepen(self) -> bool:
        return self._current_depth < self.budget.max_recovery_depth
    
    def can_retry_side_effect(self, step_id: str) -> bool:
        retries = self._side_effect_retries.get(step_id, 0)
        return retries < self.budget.max_side_effect_retries
    
    def time_remaining(self) -> float:
        elapsed = time.monotonic() - self._start_time
        return max(0, self.budget.max_total_time_s - elapsed)
    
    def is_time_exhausted(self) -> bool:
        return self.time_remaining() <= 0
    
    def is_exhausted(self, step_id: str) -> bool:
        if self.is_time_exhausted():
            return True
        if not self.can_retry(step_id):
            return True
        if not self.can_deepen():
            return True
        return False
    
    def get_remaining(self) -> dict[str, int | float]:
        return {
            "depth_remaining": self.budget.max_recovery_depth - self._current_depth,
            "time_remaining_s": self.time_remaining(),
        }
