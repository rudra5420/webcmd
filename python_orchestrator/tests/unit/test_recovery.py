"""Tests for WebCMD recovery engine."""
import pytest
from webcmd.state.enums import FailureClass, RecoveryStatus, SideEffectStatus
from webcmd.recovery.classifier import FailureClassifier
from webcmd.recovery.budget import BudgetTracker, RecoveryBudget
from webcmd.recovery.engine import RecoveryEngine
from webcmd.recovery.strategies import RecoveryAction
from webcmd.workers.base import TransientError, PermanentError, NeedsHumanError
from webcmd.workers.types import WorkerResult


class TestFailureClassifier:
    def test_transient_error(self):
        c = FailureClassifier()
        assert c.classify_exception(TransientError("timeout")) == FailureClass.TIMEOUT
    
    def test_permanent_error(self):
        c = FailureClassifier()
        assert c.classify_exception(PermanentError("element not found")) == FailureClass.ELEMENT_NOT_FOUND
    
    def test_needs_human(self):
        c = FailureClassifier()
        assert c.classify_exception(NeedsHumanError("captcha")) == FailureClass.AUTHENTICATION
    
    def test_uncertain_result(self):
        c = FailureClassifier()
        r = WorkerResult(status="uncertain", side_effect_status=SideEffectStatus.UNKNOWN)
        assert c.classify_result(r) == FailureClass.SIDE_EFFECT_UNCERTAIN
    
    def test_unknown_error(self):
        c = FailureClassifier()
        assert c.classify_exception(RuntimeError("something")) == FailureClass.UNKNOWN


class TestBudgetTracker:
    def test_retry_limit(self):
        bt = BudgetTracker(RecoveryBudget(max_attempts_per_step=2))
        assert bt.can_retry("s1")
        bt.record_attempt("s1")
        assert bt.can_retry("s1")
        bt.record_attempt("s1")
        assert not bt.can_retry("s1")
    
    def test_depth_limit(self):
        bt = BudgetTracker(RecoveryBudget(max_recovery_depth=1))
        assert bt.can_deepen()
        bt.enter_recovery()
        assert not bt.can_deepen()
        bt.exit_recovery()
        assert bt.can_deepen()


class TestRecoveryEngine:
    async def test_transient_retry(self):
        engine = RecoveryEngine()
        result = await engine.handle_failure("s1", error=TransientError("timeout"))
        assert result.should_retry_step
        assert result.action_taken == RecoveryAction.RETRY
    
    async def test_element_not_found_adapt(self):
        engine = RecoveryEngine()
        result = await engine.handle_failure("s1", error=PermanentError("element not found"))
        assert result.action_taken == RecoveryAction.ADAPT_LOCATOR
    
    async def test_auth_escalation(self):
        engine = RecoveryEngine()
        result = await engine.handle_failure("s1", error=NeedsHumanError("MFA"))
        assert result.action_taken == RecoveryAction.HUMAN_ESCALATION
    
    async def test_uncertain_side_effect(self):
        engine = RecoveryEngine()
        result = await engine.handle_failure("s1", error=Exception("crash"), side_effect_status=SideEffectStatus.UNKNOWN)
        assert result.status == RecoveryStatus.VERIFYING_EXTERNAL_STATE
    
    async def test_budget_exhaustion(self):
        engine = RecoveryEngine(RecoveryBudget(max_attempts_per_step=1))
        await engine.handle_failure("s1", error=TransientError("fail"))
        result = await engine.handle_failure("s1", error=TransientError("fail again"))
        assert result.status == RecoveryStatus.ESCALATED
