"""Tests for WebCMD security system."""
import pytest
from pathlib import Path
from uuid import uuid4

from webcmd.state.enums import RiskLevel, PolicyDecision
from webcmd.security.policy import (
    PolicyEngine, PolicyConfig, PolicyRule,
    PolicyEvaluationRequest, PolicyEvaluationResult,
)
from webcmd.security.capabilities import get_risk_level
from webcmd.security.credentials import CredentialVault
from webcmd.security.audit import AuditLogger, AuditEntry


class TestPolicyEngine:
    def test_default_allows(self):
        engine = PolicyEngine()
        result = engine.evaluate(PolicyEvaluationRequest(
            capability="browser.navigate",
            resource="https://example.com",
        ))
        assert result.decision == PolicyDecision.ALLOW
    
    def test_blocked_domain(self):
        config = PolicyConfig(rules=[PolicyRule(
            name="test", blocked_domains=["malware.com"]
        )])
        engine = PolicyEngine(config)
        result = engine.evaluate(PolicyEvaluationRequest(
            capability="browser.navigate",
            domain="malware.com",
        ))
        assert result.decision == PolicyDecision.DENY
    
    def test_critical_requires_approval(self):
        engine = PolicyEngine()
        result = engine.evaluate(PolicyEvaluationRequest(
            capability="browser.purchase",
            risk_level=RiskLevel.CRITICAL,
        ))
        assert result.decision == PolicyDecision.APPROVAL_REQUIRED
    
    def test_shadow_mode(self):
        config = PolicyConfig(
            rules=[PolicyRule(name="test", blocked_domains=["blocked.com"])],
            shadow_mode=True,
        )
        engine = PolicyEngine(config)
        result = engine.evaluate(PolicyEvaluationRequest(
            capability="browser.navigate", domain="blocked.com",
        ))
        assert result.decision == PolicyDecision.ALLOW
        assert result.shadow_mode
    
    def test_filesystem_root_restriction(self):
        config = PolicyConfig(rules=[PolicyRule(
            name="test", filesystem_roots=["/safe/dir"]
        )])
        engine = PolicyEngine(config)
        result = engine.evaluate(PolicyEvaluationRequest(
            capability="filesystem.write", resource="/unsafe/path/file.txt",
        ))
        assert result.decision == PolicyDecision.DENY
    
    def test_shell_allowlist(self):
        config = PolicyConfig(rules=[PolicyRule(
            name="test", shell_command_allowlist=["ls", "cat"]
        )])
        engine = PolicyEngine(config)
        result = engine.evaluate(PolicyEvaluationRequest(
            capability="shell.execute",
            parameters={"command": "rm -rf /"},
        ))
        assert result.decision == PolicyDecision.DENY


class TestCapabilities:
    def test_risk_levels(self):
        assert get_risk_level("browser.navigate") == RiskLevel.LOW
        assert get_risk_level("filesystem.delete") == RiskLevel.HIGH
        assert get_risk_level("browser.purchase") == RiskLevel.CRITICAL


class TestCredentialVault:
    def test_store_and_retrieve(self):
        vault = CredentialVault()
        vault.store("test_key", "secret_value")
        assert vault.retrieve("test_key") == "secret_value"
    
    def test_delete(self):
        vault = CredentialVault()
        vault.store("temp", "value")
        vault.delete("temp")
        assert not vault.exists("temp")


class TestAuditLogger:
    def test_log_and_read(self, tmp_path: Path):
        log_path = tmp_path / "audit.jsonl"
        audit = AuditLogger(log_path)
        audit.log_policy_decision(
            execution_id=uuid4(),
            capability="browser.navigate",
            resource="https://example.com",
            decision="allow",
            reason="No violations",
        )
        entries = audit.get_entries()
        assert len(entries) == 1
        assert entries[0].event_type == "policy_decision"
