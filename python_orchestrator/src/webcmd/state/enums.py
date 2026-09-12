"""WebCMD status enumerations.

All state values used across the system. Centralized to prevent
different modules from inventing their own status semantics.
"""
from __future__ import annotations
from enum import StrEnum


class ProjectStatus(StrEnum):
    """Project-level status."""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    """Task lifecycle status."""
    PENDING = "pending"
    INTENT_NORMALIZED = "intent_normalized"
    PLANNED = "planned"
    READY = "ready"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStatus(StrEnum):
    """Execution lifecycle status.
    
    Note: INTENT_NORMALIZED and PLANNED are Task-level states, not Execution.
    OBSERVING is a Step-level state. While a step is OBSERVING,
    execution remains RUNNING.
    """
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    VERIFYING = "verifying"
    AWAITING_HUMAN_VERIFICATION = "awaiting_human_verification"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class HumanVerificationDecision(StrEnum):
    """Decision outcome of the single final human verification gate."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class StepStatus(StrEnum):
    """Step-level status within an execution."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class VerificationStatus(StrEnum):
    """Verification outcome."""
    UNKNOWN = "unknown"
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"


class RecoveryStatus(StrEnum):
    """Recovery sub-state."""
    NONE = "none"
    NEEDED = "needed"
    CLASSIFYING = "classifying"
    VERIFYING_EXTERNAL_STATE = "verifying_external_state"
    RETRYING = "retrying"
    ADAPTING = "adapting"
    REPLANNING = "replanning"
    HANDOFF_PENDING = "handoff_pending"
    APPROVAL_PENDING = "approval_pending"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    ABORTING = "aborting"


class WorkflowStatus(StrEnum):
    """Workflow lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class WorkerRunStatus(StrEnum):
    """Worker run lifecycle."""
    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"


class HandoffStatus(StrEnum):
    """Handoff lifecycle."""
    REQUESTED = "requested"
    VALIDATED = "validated"
    PACKAGED = "packaged"
    TRANSFERRED = "transferred"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class HandoffReason(StrEnum):
    """Why a handoff is happening."""
    RECOVERY = "recovery"
    CAPABILITY_CHANGE = "capability_change"
    OPTIMIZATION = "optimization"
    POLICY = "policy"
    HUMAN_APPROVAL = "human_approval"


class FailureClass(StrEnum):
    """Typed failure classification for recovery."""
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    NETWORK = "network"
    ELEMENT_NOT_FOUND = "element_not_found"
    STATE_MISMATCH = "state_mismatch"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    POLICY_BLOCK = "policy_block"
    DATA_ERROR = "data_error"
    ENVIRONMENT_CHANGE = "environment_change"
    WORKER_CRASH = "worker_crash"
    VERIFICATION_FAILED = "verification_failed"
    SIDE_EFFECT_UNCERTAIN = "side_effect_uncertain"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    """Action risk classification."""
    LOW = "low"          # Read-only navigation, search
    MEDIUM = "medium"    # File creation, private edits
    HIGH = "high"        # Messages, deletions, settings
    CRITICAL = "critical"  # Irreversible/financial actions


class SideEffectStatus(StrEnum):
    """Whether an action had side effects."""
    NONE = "none"
    PARTIAL = "partial"
    APPLIED = "applied"
    UNKNOWN = "unknown"


class IdempotencyType(StrEnum):
    """Action idempotency declaration."""
    IDEMPOTENT = "idempotent"
    CONDITIONALLY_IDEMPOTENT = "conditionally_idempotent"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN = "unknown"


class MemoryType(StrEnum):
    """Types of experiential memory."""
    SITE = "site"
    NAVIGATION = "navigation"
    INTERACTION = "interaction"
    WORKFLOW = "workflow"
    FAILURE = "failure"
    RECOVERY = "recovery"
    ENVIRONMENT = "environment"
    LAST_KNOWN_STATE = "last_known_state"
    EXECUTION_HISTORY = "execution_history"
    USER_PREFERENCE = "user_preference"


class MemoryStatus(StrEnum):
    """Memory item lifecycle."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class TrustLevel(StrEnum):
    """Trust hierarchy for content/actions."""
    T0_USER = "t0_user"                # Highest: User / System Policy
    T1_CONTROL_PLANE = "t1_control"    # WebCMD Control Plane
    T2_WORKER_RUNTIME = "t2_worker"    # Worker Runtime
    T3_MODEL_OUTPUT = "t3_model"       # Model-Generated Plans (untrusted for perms)
    T4_TOOL_OUTPUT = "t4_tool"         # External Tool Outputs
    T5_WEB_CONTENT = "t5_web"          # Website Content (completely untrusted)


class PolicyDecision(StrEnum):
    """Policy evaluation result."""
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class ApprovalDecision(StrEnum):
    """User approval response."""
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class CheckpointTrigger(StrEnum):
    """What triggered a checkpoint."""
    POST_STEP = "post_step"
    PRE_RISK = "pre_risk"
    PERIODIC = "periodic"
    SHUTDOWN = "shutdown"
    POST_RECOVERY = "post_recovery"
    PRE_HANDOFF = "pre_handoff"
    PRE_HUMAN_VERIFICATION = "pre_human_verification"


class ObservationType(StrEnum):
    """Types of worker observations."""
    URL = "url"
    DOM_SNAPSHOT = "dom_snapshot"
    SCREENSHOT = "screenshot"
    HTTP_RESPONSE = "http_response"
    FILE_STATE = "file_state"
    SHELL_OUTPUT = "shell_output"
    PAGE_CONTENT = "page_content"
    ERROR = "error"
    CUSTOM = "custom"


class AssertionType(StrEnum):
    """Types of verification assertions."""
    URL_EQUALS = "url_equals"
    URL_CONTAINS = "url_contains"
    DOM_CONTAINS = "dom_contains"
    ELEMENT_VISIBLE = "element_visible"
    TEXT_MATCHES = "text_matches"
    FILE_EXISTS = "file_exists"
    FILE_HASH_MATCHES = "file_hash_matches"
    HTTP_STATUS = "http_status"
    RECORD_EXISTS = "record_exists"
    CUSTOM = "custom"
