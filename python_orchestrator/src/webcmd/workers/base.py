"""Base worker contract for the WebCMD execution plane.

All workers must implement this interface. The core orchestrator
depends ONLY on BaseWorker — it has zero knowledge of Playwright,
browser-use, or any specific automation library.

Architectural Rules:
1. Workers NEVER verify their own work — they only emit observations.
2. Workers cannot self-authorize actions. BLOCKED_BY_POLICY must fail immediately.
3. Workers must declare idempotency for retry safety.
4. Workers must support first-class uncertainty (status='uncertain').
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from webcmd.workers.types import (
    CapabilitySet,
    PauseResult,
    PreparedAction,
    ResumeResult,
    WorkerContext,
    WorkerResult,
)


class WorkerError(Exception):
    """Base error for all worker failures."""
    def __init__(self, message: str, retryable: bool = False):
        self.retryable = retryable
        super().__init__(message)


class TransientError(WorkerError):
    """Temporary failure that may succeed on retry."""
    def __init__(self, message: str):
        super().__init__(message, retryable=True)


class PermanentError(WorkerError):
    """Permanent failure requiring repair or alternative approach."""
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class NeedsHumanError(WorkerError):
    """Failure requiring human intervention (CAPTCHA, MFA, etc.)."""
    def __init__(self, message: str, action_required: str = ""):
        self.action_required = action_required
        super().__init__(message, retryable=False)


class StateMismatchError(WorkerError):
    """Environment state does not match expected preconditions."""
    def __init__(self, message: str, expected: str = "", actual: str = ""):
        self.expected = expected
        self.actual = actual
        super().__init__(message, retryable=False)


class BaseWorker(ABC):
    """Abstract base class for all WebCMD workers.
    
    Lifecycle:
        CREATED → initialize() → READY → prepare() → execute() → observe() → DONE
    
    Workers do NOT verify outcomes. They emit observations.
    The VerificationEngine evaluates assertions against those observations.
    """
    
    @property
    @abstractmethod
    def worker_type(self) -> str:
        """Unique type identifier for this worker (e.g., 'browser.playwright')."""
        ...
    
    @property
    @abstractmethod  
    def worker_name(self) -> str:
        """Human-readable name."""
        ...
    
    @abstractmethod
    async def initialize(self, context: WorkerContext) -> None:
        """Initialize the worker with execution context.
        
        Set up resources (browser instances, HTTP clients, etc.).
        Must be called before any other method.
        """
        ...
    
    @abstractmethod
    async def capabilities(self) -> CapabilitySet:
        """Declare what this worker can do.
        
        Returns the full set of capabilities this worker supports.
        Used by the ExecutionRouter for step-to-worker matching.
        """
        ...
    
    @abstractmethod
    async def prepare(self, action: PreparedAction, context: WorkerContext) -> PreparedAction:
        """Validate and refine a prepared action before execution.
        
        May enrich the action with worker-specific details
        (resolved selectors, URLs, etc.).
        
        Raises WorkerError if the action cannot be prepared.
        """
        ...
    
    @abstractmethod
    async def execute(self, action: PreparedAction, context: WorkerContext) -> WorkerResult:
        """Execute the prepared action.
        
        Returns a WorkerResult with status, outputs, and observations.
        NEVER returns verification judgments — only raw evidence.
        """
        ...
    
    @abstractmethod
    async def observe(self, context: WorkerContext) -> list:
        """Capture current state observations.
        
        Returns a list of ObservationRecord objects representing
        the current state of the execution environment.
        """
        ...
    
    @abstractmethod
    async def pause(self) -> PauseResult:
        """Pause the worker, preserving state for later resume."""
        ...
    
    @abstractmethod
    async def resume(self, context: WorkerContext) -> ResumeResult:
        """Resume the worker from a paused state."""
        ...
    
    @abstractmethod
    async def cancel(self, reason: str) -> None:
        """Cancel current operation with the given reason."""
        ...
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Release all resources and shut down the worker."""
        ...
