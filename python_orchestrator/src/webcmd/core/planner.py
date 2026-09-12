import uuid
from typing import Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from webcmd.core.intent import IntentSpec

class AssertionSpec(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    condition: str
    expected_value: Any
    tolerance: float | None = None

class VerificationSpec(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    assertions: list[AssertionSpec] = Field(default_factory=list)

class Step(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    sequence: int
    name: str
    objective: str
    required_capabilities: list[str] = Field(default_factory=list)
    action_spec: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "LOW"
    verification_spec: VerificationSpec = Field(default_factory=VerificationSpec)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Planner:
    """
    Decomposes goals into a sequential list of Step objects.
    """
    def plan(self, intent: IntentSpec, memory_hints: list[dict[str, Any]] | None = None) -> list[Step]:
        """
        Generates steps to fulfill the intent. Reuses known workflows from memory_hints if applicable.
        """
        if memory_hints:
            # If memory hints are provided, try to reconstruct steps from them
            # For simplicity, returning a mock step reconstructed from hint
            steps = []
            for i, hint in enumerate(memory_hints):
                steps.append(
                    Step(
                        sequence=i+1,
                        name=hint.get("name", f"Hint Step {i+1}"),
                        objective=hint.get("objective", "Execute hint step"),
                        required_capabilities=hint.get("required_capabilities", ["browser.navigate"]),
                        action_spec=hint.get("action_spec", {}),
                        risk_level=intent.risk_level
                    )
                )
            if steps:
                return steps

        # Generate from scratch
        step1 = Step(
            sequence=1,
            name="Initial navigation",
            objective="Navigate to target URL",
            required_capabilities=["browser.navigate"],
            action_spec={"url": intent.target_urls[0] if intent.target_urls else "https://example.com"},
            risk_level=intent.risk_level,
            verification_spec=VerificationSpec(
                assertions=[AssertionSpec(condition="url_equals", expected_value=intent.target_urls[0] if intent.target_urls else "https://example.com")]
            )
        )
        return [step1]
