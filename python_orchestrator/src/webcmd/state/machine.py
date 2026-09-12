from enum import StrEnum
from typing import Any, Dict, Set

class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, entity_type: str, current: str, target: str, reason: str = ""):
        self.entity_type = entity_type
        self.current = current
        self.target = target
        self.reason = reason
        super().__init__(f"{entity_type}: invalid transition {current} → {target}. {reason}")

class ExecutionState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    AWAITING_HUMAN_VERIFICATION = "AWAITING_HUMAN_VERIFICATION"
    RECOVERING = "RECOVERING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class StepState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    UNCERTAIN = "UNCERTAIN"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class RecoveryState(StrEnum):
    NONE = "NONE"
    NEEDED = "NEEDED"
    CLASSIFYING = "CLASSIFYING"
    VERIFYING_EXTERNAL_STATE = "VERIFYING_EXTERNAL_STATE"
    RETRYING = "RETRYING"
    ADAPTING = "ADAPTING"
    REPLANNING = "REPLANNING"
    HANDOFF_PENDING = "HANDOFF_PENDING"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    ABORTING = "ABORTING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"

class StateMachine:
    """Base state machine."""
    entity_type = "Base"
    transitions: Dict[str, Set[str]] = {}

    @classmethod
    def transition(cls, current: Any, target: Any, reason: str = "") -> Any:
        """Validate and transition to a new state."""
        curr_str = str(getattr(current, "value", current)).lower()
        target_str = str(getattr(target, "value", target)).lower()

        norm_transitions = {
            str(k).lower(): {str(v).lower() for v in vals}
            for k, vals in cls.transitions.items()
        }
        allowed_targets = norm_transitions.get(curr_str, set())
        if target_str not in allowed_targets:
            raise InvalidStateTransitionError(cls.entity_type, str(current), str(target), reason)
        return target

class ExecutionStateMachine(StateMachine):
    """State machine for Executions."""
    entity_type = "Execution"
    transitions = {
        ExecutionState.PENDING: {ExecutionState.READY},
        ExecutionState.READY: {ExecutionState.RUNNING, ExecutionState.CANCELLED},
        ExecutionState.RUNNING: {ExecutionState.VERIFYING, ExecutionState.FAILED, ExecutionState.RECOVERING, ExecutionState.PAUSED, ExecutionState.CANCELLED, ExecutionState.WAITING},
        ExecutionState.WAITING: {ExecutionState.RUNNING, ExecutionState.CANCELLED},
        ExecutionState.VERIFYING: {ExecutionState.AWAITING_HUMAN_VERIFICATION, ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.RUNNING},
        ExecutionState.AWAITING_HUMAN_VERIFICATION: {ExecutionState.COMPLETED, ExecutionState.RECOVERING, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.PAUSED},
        ExecutionState.RECOVERING: {ExecutionState.RUNNING, ExecutionState.AWAITING_HUMAN_VERIFICATION, ExecutionState.FAILED, ExecutionState.PAUSED, ExecutionState.CANCELLED, ExecutionState.BLOCKED},
        ExecutionState.PAUSED: {ExecutionState.RUNNING, ExecutionState.CANCELLED},
        ExecutionState.BLOCKED: {ExecutionState.RUNNING, ExecutionState.CANCELLED, ExecutionState.FAILED},
        ExecutionState.COMPLETED: set(),
        ExecutionState.FAILED: set(),
        ExecutionState.CANCELLED: set()
    }

class StepStateMachine(StateMachine):
    """State machine for Steps."""
    entity_type = "Step"
    transitions = {
        StepState.PENDING: {StepState.READY},
        StepState.READY: {StepState.RUNNING, StepState.SKIPPED, StepState.BLOCKED},
        StepState.RUNNING: {StepState.OBSERVING, StepState.FAILED, StepState.UNCERTAIN, StepState.BLOCKED},
        StepState.OBSERVING: {StepState.VERIFYING, StepState.FAILED},
        StepState.VERIFYING: {StepState.COMPLETED, StepState.FAILED},
        StepState.UNCERTAIN: {StepState.RUNNING, StepState.FAILED},
        StepState.BLOCKED: {StepState.READY, StepState.SKIPPED, StepState.FAILED},
        StepState.SKIPPED: set(),
        StepState.COMPLETED: set(),
        StepState.FAILED: set()
    }

class RecoveryStateMachine(StateMachine):
    """State machine for Recovery logic."""
    entity_type = "Recovery"
    transitions = {
        RecoveryState.NONE: {RecoveryState.NEEDED},
        RecoveryState.NEEDED: {RecoveryState.CLASSIFYING},
        RecoveryState.CLASSIFYING: {RecoveryState.VERIFYING_EXTERNAL_STATE, RecoveryState.RETRYING, RecoveryState.ADAPTING, RecoveryState.REPLANNING, RecoveryState.HANDOFF_PENDING, RecoveryState.APPROVAL_PENDING, RecoveryState.ABORTING},
        RecoveryState.VERIFYING_EXTERNAL_STATE: {RecoveryState.RETRYING, RecoveryState.ADAPTING, RecoveryState.REPLANNING, RecoveryState.HANDOFF_PENDING, RecoveryState.APPROVAL_PENDING, RecoveryState.ABORTING, RecoveryState.RESOLVED},
        RecoveryState.RETRYING: {RecoveryState.RESOLVED, RecoveryState.NEEDED, RecoveryState.ABORTING},
        RecoveryState.ADAPTING: {RecoveryState.RESOLVED, RecoveryState.NEEDED, RecoveryState.ABORTING},
        RecoveryState.REPLANNING: {RecoveryState.RESOLVED, RecoveryState.NEEDED, RecoveryState.ABORTING, RecoveryState.HANDOFF_PENDING},
        RecoveryState.HANDOFF_PENDING: {RecoveryState.RESOLVED, RecoveryState.ESCALATED, RecoveryState.ABORTING},
        RecoveryState.APPROVAL_PENDING: {RecoveryState.RESOLVED, RecoveryState.ESCALATED, RecoveryState.ABORTING},
        RecoveryState.ABORTING: {RecoveryState.ESCALATED},
        RecoveryState.RESOLVED: set(),
        RecoveryState.ESCALATED: set()
    }
