import uuid
from typing import Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class IntentSpec(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    prompt: str
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    target_urls: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "LOW"
    project_id: uuid.UUID | None = None
    context: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class IntentEngine:
    """
    Engine to normalize user prompts into structured IntentSpec objects.
    """
    def __init__(self):
        self.critical_keywords = {"buy", "purchase", "pay", "checkout", "transfer", "wire"}
        self.high_keywords = {"delete", "remove", "post", "publish", "drop", "destroy", "tweet"}
        self.medium_keywords = {"download", "write", "edit", "update", "modify", "save", "upload"}
        self.low_keywords = {"read", "navigate", "view", "get", "fetch", "search", "find"}

    def _assess_risk(self, prompt: str) -> str:
        """
        Assess risk level using keyword rules.
        """
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in self.critical_keywords):
            return "CRITICAL"
        if any(kw in prompt_lower for kw in self.high_keywords):
            return "HIGH"
        if any(kw in prompt_lower for kw in self.medium_keywords):
            return "MEDIUM"
        return "LOW"

    def normalize(self, prompt: str, project_id: uuid.UUID | None = None, context: dict[str, Any] | None = None) -> IntentSpec:
        """
        Extracts actionable goals, constraints, target URLs/domains, parameter inputs.
        Assesses risk level.
        """
        goals = [f"Achieve: {prompt}"]
        words = prompt.split()
        target_urls = [w for w in words if w.startswith("http://") or w.startswith("https://")]
        risk = self._assess_risk(prompt)
        
        return IntentSpec(
            prompt=prompt,
            goals=goals,
            constraints=[],
            target_urls=target_urls,
            parameters={},
            risk_level=risk,
            project_id=project_id,
            context=context or {}
        )
