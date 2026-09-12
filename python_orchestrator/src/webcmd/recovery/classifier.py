"""Failure classification for the WebCMD recovery engine.

Maps raw exceptions, error codes, and worker results to one of
14 typed FailureClass values. The classification determines
which recovery strategy is applied.
"""
from __future__ import annotations
import logging
from webcmd.state.enums import FailureClass
from webcmd.workers.base import (
    WorkerError,
    TransientError,
    PermanentError,
    NeedsHumanError,
    StateMismatchError,
)
from webcmd.workers.types import WorkerResult

logger = logging.getLogger(__name__)


class FailureClassifier:
    """Classifies failures into typed categories for recovery routing."""
    
    # Map known error messages to failure classes
    _ERROR_PATTERNS: dict[str, FailureClass] = {
        "timeout": FailureClass.TIMEOUT,
        "timed out": FailureClass.TIMEOUT,
        "network": FailureClass.NETWORK,
        "connection": FailureClass.NETWORK,
        "dns": FailureClass.NETWORK,
        "not found": FailureClass.ELEMENT_NOT_FOUND,
        "no such element": FailureClass.ELEMENT_NOT_FOUND,
        "selector": FailureClass.ELEMENT_NOT_FOUND,
        "locator": FailureClass.ELEMENT_NOT_FOUND,
        "authentication": FailureClass.AUTHENTICATION,
        "login": FailureClass.AUTHENTICATION,
        "401": FailureClass.AUTHENTICATION,
        "403": FailureClass.PERMISSION,
        "permission": FailureClass.PERMISSION,
        "access denied": FailureClass.PERMISSION,
        "policy": FailureClass.POLICY_BLOCK,
        "blocked": FailureClass.POLICY_BLOCK,
        "data": FailureClass.DATA_ERROR,
        "validation": FailureClass.DATA_ERROR,
        "schema": FailureClass.DATA_ERROR,
        "crash": FailureClass.WORKER_CRASH,
        "segfault": FailureClass.WORKER_CRASH,
        "verification": FailureClass.VERIFICATION_FAILED,
        "mismatch": FailureClass.STATE_MISMATCH,
        "state": FailureClass.STATE_MISMATCH,
    }
    
    def classify_exception(self, error: Exception) -> FailureClass:
        """Classify an exception into a FailureClass."""
        if isinstance(error, TransientError):
            # Check for specific transient subtypes
            msg = str(error).lower()
            if "timeout" in msg:
                return FailureClass.TIMEOUT
            if "network" in msg or "connection" in msg:
                return FailureClass.NETWORK
            return FailureClass.TRANSIENT
        
        if isinstance(error, PermanentError):
            msg = str(error).lower()
            if "not found" in msg or "element" in msg:
                return FailureClass.ELEMENT_NOT_FOUND
            if "auth" in msg:
                return FailureClass.AUTHENTICATION
            if "permission" in msg:
                return FailureClass.PERMISSION
            return FailureClass.ENVIRONMENT_CHANGE
        
        if isinstance(error, NeedsHumanError):
            return FailureClass.AUTHENTICATION  # CAPTCHA, MFA, etc.
        
        if isinstance(error, StateMismatchError):
            return FailureClass.STATE_MISMATCH
        
        if isinstance(error, WorkerError):
            return FailureClass.WORKER_CRASH
        
        # Classify by error message patterns
        msg = str(error).lower()
        for pattern, fc in self._ERROR_PATTERNS.items():
            if pattern in msg:
                return fc
        
        return FailureClass.UNKNOWN
    
    def classify_result(self, result: WorkerResult) -> FailureClass:
        """Classify a failed/uncertain WorkerResult into a FailureClass."""
        if result.status == "uncertain":
            return FailureClass.SIDE_EFFECT_UNCERTAIN
        
        code = (result.failure_code or "").lower()
        msg = (result.failure_message or "").lower()
        
        combined = f"{code} {msg}"
        for pattern, fc in self._ERROR_PATTERNS.items():
            if pattern in combined:
                return fc
        
        if result.retryable:
            return FailureClass.TRANSIENT
        
        return FailureClass.UNKNOWN
