"""WebCMD Recovery Engine.

Orchestrates the self-healing recovery process:
    Failure -> Classify -> Verify Side Effects -> Select Strategy -> Execute -> Verify

Recovery is BOUNDED by multi-dimensional budgets to prevent infinite loops.
"""
from __future__ import annotations
import logging
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field
from webcmd.state.enums import FailureClass, RecoveryStatus, SideEffectStatus
from webcmd.recovery.classifier import FailureClassifier
from webcmd.recovery.budget import BudgetTracker, RecoveryBudget
from webcmd.recovery.strategies import (
    RecoveryAction,
    RecoveryRecommendation,
    RecoveryStrategy,
    RetryStrategy,
    LocatorAdaptStrategy,
    ReplanStrategy,
    HumanEscalationStrategy,
    AbortStrategy,
)

logger = logging.getLogger(__name__)


class RecoveryResult(BaseModel):
    status: RecoveryStatus
    action_taken: RecoveryAction | None = None
    failure_class: FailureClass | None = None
    message: str = ""
    should_retry_step: bool = False
    modified_parameters: dict[str, Any] = Field(default_factory=dict)


class RecoveryEngine:
    """Orchestrates bounded recovery from execution failures."""
    
    def __init__(self, budget: RecoveryBudget | None = None) -> None:
        self.classifier = FailureClassifier()
        self.budget_tracker = BudgetTracker(budget)
        self.strategies: list[RecoveryStrategy] = [
            RetryStrategy(),
            LocatorAdaptStrategy(),
            ReplanStrategy(),
            HumanEscalationStrategy(),
            AbortStrategy(),
        ]
    
    async def handle_failure(
        self,
        step_id: str,
        error: Exception | None = None,
        worker_result: Any | None = None,
        side_effect_status: SideEffectStatus = SideEffectStatus.NONE,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """Handle a step failure through the recovery pipeline."""
        ctx = context or {}
        
        # 1. Classify
        if error:
            failure_class = self.classifier.classify_exception(error)
        elif worker_result:
            from webcmd.workers.types import WorkerResult
            if isinstance(worker_result, WorkerResult):
                failure_class = self.classifier.classify_result(worker_result)
            else:
                failure_class = FailureClass.UNKNOWN
        else:
            failure_class = FailureClass.UNKNOWN
        
        logger.info(f"Classified failure for step {step_id}: {failure_class}")
        
        # 2. Check side-effect uncertainty
        if side_effect_status == SideEffectStatus.UNKNOWN:
            if not self.budget_tracker.can_retry_side_effect(step_id):
                return RecoveryResult(
                    status=RecoveryStatus.ESCALATED,
                    failure_class=FailureClass.SIDE_EFFECT_UNCERTAIN,
                    message="Side effect uncertain and retry budget exhausted. Human verification required.",
                )
            self.budget_tracker.record_side_effect_retry(step_id)
            return RecoveryResult(
                status=RecoveryStatus.VERIFYING_EXTERNAL_STATE,
                failure_class=FailureClass.SIDE_EFFECT_UNCERTAIN,
                action_taken=RecoveryAction.RE_OBSERVE,
                message="Side effect uncertain. Probing external state before retry.",
                should_retry_step=True,
            )
        
        # 3. Check budget
        if self.budget_tracker.is_exhausted(step_id):
            return RecoveryResult(
                status=RecoveryStatus.ESCALATED,
                failure_class=failure_class,
                message=f"Recovery budget exhausted for step {step_id}",
            )
        
        # 4. Record attempt and enter recovery
        self.budget_tracker.record_attempt(step_id)
        self.budget_tracker.enter_recovery()
        
        # 5. Find strategy
        recommendation: RecoveryRecommendation | None = None
        for strategy in self.strategies:
            if strategy.can_handle(failure_class):
                recommendation = strategy.recommend(failure_class, ctx)
                break
        
        if not recommendation or recommendation.action == RecoveryAction.ABORT:
            self.budget_tracker.exit_recovery()
            return RecoveryResult(
                status=RecoveryStatus.ABORTING,
                failure_class=failure_class,
                action_taken=RecoveryAction.ABORT,
                message=f"No viable recovery strategy for {failure_class}",
            )
        
        # 6. Return recommendation (actual execution happens in orchestrator)
        self.budget_tracker.exit_recovery()
        
        should_retry = recommendation.action in (
            RecoveryAction.RETRY,
            RecoveryAction.ADAPT_LOCATOR,
            RecoveryAction.RE_OBSERVE,
        )
        
        return RecoveryResult(
            status=RecoveryStatus.RESOLVED if should_retry else RecoveryStatus.ADAPTING,
            failure_class=failure_class,
            action_taken=recommendation.action,
            message=recommendation.reason,
            should_retry_step=should_retry,
            modified_parameters=recommendation.parameters,
        )

    async def handle_human_rejection(
        self,
        execution_id: UUID,
        reason: str = "",
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """Handle human rejection of final verified result.
        
        Preserves checkpoint, classifies rejection, and initiates bounded review/recovery.
        """
        step_key = f"human_rejection_{execution_id}"
        failure_class = FailureClass.VERIFICATION_FAILED
        
        logger.warning(f"Human rejected execution {execution_id}. Reason: {reason or 'none provided'}")
        
        if self.budget_tracker.is_exhausted(step_key):
            return RecoveryResult(
                status=RecoveryStatus.ESCALATED,
                failure_class=failure_class,
                message=f"Recovery budget exhausted for execution {execution_id} after human rejection",
            )
        
        self.budget_tracker.record_attempt(step_key)
        
        return RecoveryResult(
            status=RecoveryStatus.NEEDED,
            failure_class=failure_class,
            action_taken=RecoveryAction.GLOBAL_REPLAN,
            message=f"Human rejection: {reason or 'Result rejected during final human verification'}. Recovery/review required.",
            should_retry_step=False,
            modified_parameters={"human_reason": reason},
        )
