"""WebCMD Policy Engine.

The policy engine decides what WebCMD is allowed to do.
It lives OUTSIDE the model — model output cannot grant permissions,
relax constraints, or modify policies.

Design Principle: Security lives outside the model.
"""
from __future__ import annotations
import logging
from typing import Any
from pydantic import BaseModel, Field
from webcmd.state.enums import RiskLevel, PolicyDecision, TrustLevel

logger = logging.getLogger(__name__)


class PolicyRule(BaseModel):
    """A single policy rule."""
    name: str
    description: str = ""
    allowed_domains: list[str] = Field(default_factory=list, description="Empty = all allowed")
    blocked_domains: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list, description="Empty = all allowed")
    blocked_capabilities: list[str] = Field(default_factory=list)
    max_risk_level: RiskLevel = RiskLevel.HIGH
    require_approval_for: list[RiskLevel] = Field(default_factory=lambda: [RiskLevel.CRITICAL])
    filesystem_roots: list[str] = Field(default_factory=list, description="Allowed filesystem paths")
    shell_command_allowlist: list[str] = Field(default_factory=list, description="Allowed shell commands")


class PolicyConfig(BaseModel):
    """Complete policy configuration."""
    rules: list[PolicyRule] = Field(default_factory=lambda: [PolicyRule(name="default")])
    shadow_mode: bool = Field(default=False, description="If true, evaluate but don't block")
    audit_all: bool = Field(default=True)


class PolicyEvaluationRequest(BaseModel):
    """Request to evaluate a policy decision."""
    capability: str
    resource: str = ""
    action: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    domain: str | None = None
    trust_level: TrustLevel = TrustLevel.T3_MODEL_OUTPUT
    parameters: dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluationResult(BaseModel):
    """Result of a policy evaluation."""
    decision: PolicyDecision
    rule_name: str = ""
    reason: str = ""
    shadow_mode: bool = False
    requires_approval_scope: str | None = None


class PolicyEngine:
    """Authoritative policy evaluation engine.
    
    The LLM proposes actions. This engine decides whether they're allowed.
    """
    
    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig()
    
    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResult:
        """Evaluate whether an action is permitted."""
        for rule in self.config.rules:
            result = self._evaluate_against_rule(request, rule)
            if result.decision != PolicyDecision.ALLOW:
                if self.config.shadow_mode:
                    logger.warning(
                        f"SHADOW MODE: Would {result.decision} "
                        f"'{request.capability}' on '{request.resource}': {result.reason}"
                    )
                    return PolicyEvaluationResult(
                        decision=PolicyDecision.ALLOW,
                        rule_name=result.rule_name,
                        reason=f"SHADOW: {result.reason}",
                        shadow_mode=True,
                    )
                return result
        
        return PolicyEvaluationResult(
            decision=PolicyDecision.ALLOW,
            rule_name="default",
            reason="No policy violations found",
        )
    
    def _evaluate_against_rule(
        self, request: PolicyEvaluationRequest, rule: PolicyRule
    ) -> PolicyEvaluationResult:
        # Check blocked domains
        if request.domain and rule.blocked_domains:
            for bd in rule.blocked_domains:
                if bd in (request.domain or ""):
                    return PolicyEvaluationResult(
                        decision=PolicyDecision.DENY,
                        rule_name=rule.name,
                        reason=f"Domain '{request.domain}' is blocked by policy",
                    )
        
        # Check allowed domains
        if request.domain and rule.allowed_domains:
            if not any(ad in request.domain for ad in rule.allowed_domains):
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    rule_name=rule.name,
                    reason=f"Domain '{request.domain}' not in allowlist",
                )
        
        # Check blocked capabilities
        if rule.blocked_capabilities:
            if request.capability in rule.blocked_capabilities:
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    rule_name=rule.name,
                    reason=f"Capability '{request.capability}' is blocked",
                )
        
        # Check approval requirements
        if request.risk_level in rule.require_approval_for:
            return PolicyEvaluationResult(
                decision=PolicyDecision.APPROVAL_REQUIRED,
                rule_name=rule.name,
                reason=f"Risk level {request.risk_level} requires approval",
                requires_approval_scope=f"{request.capability}:{request.resource}",
            )

        # Check risk level
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        if risk_order.index(request.risk_level) > risk_order.index(rule.max_risk_level):
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY,
                rule_name=rule.name,
                reason=f"Risk level {request.risk_level} exceeds maximum {rule.max_risk_level}",
            )
        
        # Check filesystem roots
        if request.capability.startswith("filesystem.") and rule.filesystem_roots:
            resource_path = request.resource
            if not any(resource_path.startswith(root) for root in rule.filesystem_roots):
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    rule_name=rule.name,
                    reason=f"Filesystem path '{resource_path}' outside allowed roots",
                )
        
        # Check shell command allowlist
        if request.capability == "shell.execute" and rule.shell_command_allowlist:
            cmd = request.parameters.get("command", "")
            cmd_name = cmd.split()[0] if cmd else ""
            if cmd_name not in rule.shell_command_allowlist:
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    rule_name=rule.name,
                    reason=f"Shell command '{cmd_name}' not in allowlist",
                )
        
        return PolicyEvaluationResult(
            decision=PolicyDecision.ALLOW,
            rule_name=rule.name,
            reason="Passed all checks",
        )
