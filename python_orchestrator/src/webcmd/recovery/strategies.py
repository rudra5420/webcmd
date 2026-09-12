"""Recovery strategy implementations.

Each strategy handles a specific class of failure with bounded
recovery actions. Strategies are tried in escalating order:
    Retry -> Re-observe -> Adapt -> Local Replan -> Handoff -> Human -> Abort
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field
from webcmd.state.enums import FailureClass

logger = logging.getLogger(__name__)


class RecoveryAction(StrEnum):
    RETRY = "retry"
    RE_OBSERVE = "re_observe"
    ADAPT_LOCATOR = "adapt_locator"
    LOCAL_REPLAN = "local_replan"
    GLOBAL_REPLAN = "global_replan"
    HANDOFF = "handoff"
    HUMAN_ESCALATION = "human_escalation"
    ABORT = "abort"


class RecoveryRecommendation(BaseModel):
    action: RecoveryAction
    reason: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RecoveryStrategy(ABC):
    @abstractmethod
    def can_handle(self, failure_class: FailureClass) -> bool: ...
    @abstractmethod
    def recommend(self, failure_class: FailureClass, context: dict[str, Any]) -> RecoveryRecommendation: ...


class RetryStrategy(RecoveryStrategy):
    def can_handle(self, fc: FailureClass) -> bool:
        return fc in (FailureClass.TRANSIENT, FailureClass.TIMEOUT, FailureClass.NETWORK)
    def recommend(self, fc: FailureClass, context: dict) -> RecoveryRecommendation:
        wait = {FailureClass.TRANSIENT: 1.0, FailureClass.TIMEOUT: 5.0, FailureClass.NETWORK: 3.0}
        return RecoveryRecommendation(
            action=RecoveryAction.RETRY,
            reason=f"Transient failure ({fc}), retry with backoff",
            parameters={"wait_seconds": wait.get(fc, 2.0)},
            confidence=0.7,
        )


class LocatorAdaptStrategy(RecoveryStrategy):
    def can_handle(self, fc: FailureClass) -> bool:
        return fc in (FailureClass.ELEMENT_NOT_FOUND, FailureClass.ENVIRONMENT_CHANGE)
    def recommend(self, fc: FailureClass, context: dict) -> RecoveryRecommendation:
        return RecoveryRecommendation(
            action=RecoveryAction.ADAPT_LOCATOR,
            reason="Element not found, try alternative locator strategy",
            parameters={"try_strategies": ["aria", "text", "css", "visual"]},
            confidence=0.5,
        )


class ReplanStrategy(RecoveryStrategy):
    def can_handle(self, fc: FailureClass) -> bool:
        return fc in (FailureClass.STATE_MISMATCH, FailureClass.DATA_ERROR, FailureClass.VERIFICATION_FAILED)
    def recommend(self, fc: FailureClass, context: dict) -> RecoveryRecommendation:
        return RecoveryRecommendation(
            action=RecoveryAction.LOCAL_REPLAN,
            reason=f"State mismatch ({fc}), replan this step",
            confidence=0.4,
        )


class HumanEscalationStrategy(RecoveryStrategy):
    def can_handle(self, fc: FailureClass) -> bool:
        return fc in (FailureClass.AUTHENTICATION, FailureClass.PERMISSION, FailureClass.POLICY_BLOCK)
    def recommend(self, fc: FailureClass, context: dict) -> RecoveryRecommendation:
        return RecoveryRecommendation(
            action=RecoveryAction.HUMAN_ESCALATION,
            reason=f"Human intervention required ({fc})",
            confidence=0.9,
        )


class AbortStrategy(RecoveryStrategy):
    def can_handle(self, fc: FailureClass) -> bool:
        return True  # Fallback
    def recommend(self, fc: FailureClass, context: dict) -> RecoveryRecommendation:
        return RecoveryRecommendation(
            action=RecoveryAction.ABORT,
            reason=f"Unrecoverable failure ({fc})",
            confidence=1.0,
        )
