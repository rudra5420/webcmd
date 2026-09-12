"""WebCMD Verification Engine.

The Truth Engine. Evaluates postcondition assertions against
worker observations to determine if a step actually achieved
its intended outcome.

Architectural Rule:
    Workers NEVER verify their own work. They only emit observations.
    This engine independently evaluates whether the intended state
    was actually achieved.

Design:
    - Each assertion has a type (url_equals, file_exists, etc.)
    - Each assertion is evaluated against collected observations
    - Results include confidence and evidence references
    - Verification failure ≠ worker failure (action can succeed but not achieve intent)
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from webcmd.state.enums import AssertionType, VerificationStatus
from webcmd.workers.types import ObservationRecord

logger = logging.getLogger(__name__)


class AssertionSpec(BaseModel):
    """A single assertion to verify."""
    assertion_type: AssertionType
    description: str = Field(default="")
    expected: dict[str, Any] = Field(default_factory=dict)
    required: bool = Field(default=True, description="If False, failure is warning not error")


class AssertionResult(BaseModel):
    """Result of evaluating a single assertion."""
    assertion_id: UUID = Field(default_factory=uuid4)
    assertion_type: AssertionType
    description: str = ""
    passed: bool
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    expected: dict[str, Any] = Field(default_factory=dict)
    actual: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list, description="Observation IDs used")
    message: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerificationResult(BaseModel):
    """Overall verification result for a step or execution."""
    status: VerificationStatus
    assertions: list[AssertionResult] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    total_count: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerificationEngine:
    """Central verification engine.
    
    Evaluates assertion specs against observations collected
    from worker execution. Independent of execution logic.
    """
    
    def __init__(self) -> None:
        self._evaluators: dict[AssertionType, Any] = {
            AssertionType.URL_EQUALS: self._eval_url_equals,
            AssertionType.URL_CONTAINS: self._eval_url_contains,
            AssertionType.DOM_CONTAINS: self._eval_dom_contains,
            AssertionType.ELEMENT_VISIBLE: self._eval_element_visible,
            AssertionType.TEXT_MATCHES: self._eval_text_matches,
            AssertionType.FILE_EXISTS: self._eval_file_exists,
            AssertionType.FILE_HASH_MATCHES: self._eval_file_hash_matches,
            AssertionType.HTTP_STATUS: self._eval_http_status,
            AssertionType.RECORD_EXISTS: self._eval_record_exists,
            AssertionType.CUSTOM: self._eval_custom,
        }
    
    async def evaluate(
        self,
        assertions: list[AssertionSpec],
        observations: list[ObservationRecord],
    ) -> VerificationResult:
        """Evaluate all assertions against collected observations.
        
        Args:
            assertions: List of expected conditions to verify.
            observations: Evidence collected from worker execution.
        
        Returns:
            VerificationResult with individual assertion outcomes.
        """
        if not assertions:
            return VerificationResult(
                status=VerificationStatus.PASS,
                confidence=1.0,
                message="No assertions to verify",
            )
        
        results: list[AssertionResult] = []
        
        for spec in assertions:
            evaluator = self._evaluators.get(spec.assertion_type)
            if evaluator:
                result = await evaluator(spec, observations)
            else:
                result = AssertionResult(
                    assertion_type=spec.assertion_type,
                    description=spec.description,
                    passed=False,
                    confidence=0.0,
                    message=f"No evaluator for assertion type: {spec.assertion_type}",
                )
            results.append(result)
        
        passed = sum(1 for r in results if r.passed)
        failed_required = sum(1 for r, s in zip(results, assertions) if not r.passed and s.required)
        total = len(results)
        
        if failed_required > 0:
            status = VerificationStatus.FAIL
        elif passed == total:
            status = VerificationStatus.PASS
        else:
            status = VerificationStatus.PARTIAL
        
        avg_confidence = sum(r.confidence for r in results) / total if total > 0 else 0.0
        
        return VerificationResult(
            status=status,
            assertions=results,
            passed_count=passed,
            failed_count=total - passed,
            total_count=total,
            confidence=avg_confidence,
            message=f"{passed}/{total} assertions passed",
        )
    
    def _find_observations(
        self, observations: list[ObservationRecord], obs_type: str
    ) -> list[ObservationRecord]:
        """Filter observations by type."""
        return [o for o in observations if o.observation_type == obs_type]
    
    async def _eval_url_equals(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        expected_url = spec.expected.get("url", "")
        url_obs = self._find_observations(observations, "url")
        
        if not url_obs:
            return AssertionResult(
                assertion_type=spec.assertion_type,
                description=spec.description,
                passed=False,
                confidence=0.0,
                expected={"url": expected_url},
                actual={"url": None},
                message="No URL observation found",
            )
        
        actual_url = url_obs[-1].data.get("url", "")
        passed = actual_url == expected_url
        
        return AssertionResult(
            assertion_type=spec.assertion_type,
            description=spec.description,
            passed=passed,
            confidence=1.0 if passed else 0.0,
            expected={"url": expected_url},
            actual={"url": actual_url},
            message="URL matches" if passed else f"URL mismatch: expected '{expected_url}', got '{actual_url}'",
        )
    
    async def _eval_url_contains(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        substring = spec.expected.get("substring", "")
        url_obs = self._find_observations(observations, "url")
        
        if not url_obs:
            return AssertionResult(
                assertion_type=spec.assertion_type, description=spec.description,
                passed=False, confidence=0.0, message="No URL observation found",
            )
        
        actual_url = url_obs[-1].data.get("url", "")
        passed = substring in actual_url
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=passed, confidence=1.0 if passed else 0.0,
            expected={"substring": substring}, actual={"url": actual_url},
            message="URL contains substring" if passed else "URL does not contain substring",
        )
    
    async def _eval_dom_contains(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        search_text = spec.expected.get("text", "")
        dom_obs = self._find_observations(observations, "dom_snapshot") + \
                  self._find_observations(observations, "page_content")
        
        if not dom_obs:
            return AssertionResult(
                assertion_type=spec.assertion_type, description=spec.description,
                passed=False, confidence=0.0, message="No DOM observation found",
            )
        
        content = dom_obs[-1].data.get("content", "") or dom_obs[-1].data.get("html", "")
        passed = search_text.lower() in content.lower()
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=passed, confidence=1.0 if passed else 0.0,
            expected={"text": search_text},
            message="DOM contains text" if passed else "Text not found in DOM",
        )
    
    async def _eval_element_visible(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        selector = spec.expected.get("selector", "")
        dom_obs = self._find_observations(observations, "dom_snapshot")
        
        if not dom_obs:
            return AssertionResult(
                assertion_type=spec.assertion_type, description=spec.description,
                passed=False, confidence=0.0, message="No DOM observation found",
            )
        
        # Check if element info exists in observations
        elements = dom_obs[-1].data.get("visible_elements", [])
        passed = any(selector in str(el) for el in elements)
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=passed, confidence=0.8 if passed else 0.2,
            expected={"selector": selector},
            message="Element found" if passed else f"Element '{selector}' not visible",
        )
    
    async def _eval_text_matches(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        pattern = spec.expected.get("pattern", "")
        text_obs = self._find_observations(observations, "page_content") + \
                   self._find_observations(observations, "shell_output")
        
        if not text_obs:
            return AssertionResult(
                assertion_type=spec.assertion_type, description=spec.description,
                passed=False, confidence=0.0, message="No text observation found",
            )
        
        content = text_obs[-1].data.get("content", "") or text_obs[-1].data.get("output", "")
        try:
            passed = bool(re.search(pattern, content, re.IGNORECASE))
        except re.error:
            passed = pattern.lower() in content.lower()
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=passed, confidence=1.0 if passed else 0.0,
            expected={"pattern": pattern},
            message="Text matches pattern" if passed else "Text does not match",
        )
    
    async def _eval_file_exists(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        file_path = spec.expected.get("path", "")
        
        # Check file observations first
        file_obs = self._find_observations(observations, "file_state")
        if file_obs:
            obs_path = file_obs[-1].data.get("path", "")
            exists = file_obs[-1].data.get("exists", False)
            if obs_path == file_path:
                return AssertionResult(
                    assertion_type=spec.assertion_type, description=spec.description,
                    passed=exists, confidence=1.0,
                    expected={"path": file_path}, actual={"exists": exists},
                    message="File exists" if exists else "File does not exist",
                )
        
        # Direct filesystem check as fallback
        exists = Path(file_path).exists() if file_path else False
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=exists, confidence=1.0 if exists else 0.9,
            expected={"path": file_path}, actual={"exists": exists},
            message="File exists" if exists else "File not found",
        )
    
    async def _eval_file_hash_matches(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        file_path = spec.expected.get("path", "")
        expected_hash = spec.expected.get("hash", "")
        algorithm = spec.expected.get("algorithm", "sha256")
        
        if not file_path or not Path(file_path).exists():
            return AssertionResult(
                assertion_type=spec.assertion_type, description=spec.description,
                passed=False, confidence=1.0,
                expected={"hash": expected_hash},
                message="File not found for hash verification",
            )
        
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        actual_hash = h.hexdigest()
        passed = actual_hash == expected_hash
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=passed, confidence=1.0,
            expected={"hash": expected_hash}, actual={"hash": actual_hash},
            message="Hash matches" if passed else "Hash mismatch",
        )
    
    async def _eval_http_status(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        expected_status = spec.expected.get("status_code", 200)
        http_obs = self._find_observations(observations, "http_response")
        
        if not http_obs:
            return AssertionResult(
                assertion_type=spec.assertion_type, description=spec.description,
                passed=False, confidence=0.0,
                message="No HTTP response observation found",
            )
        
        actual_status = http_obs[-1].data.get("status_code", 0)
        passed = actual_status == expected_status
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=passed, confidence=1.0,
            expected={"status_code": expected_status},
            actual={"status_code": actual_status},
            message=f"HTTP {actual_status}" if passed else f"Expected HTTP {expected_status}, got {actual_status}",
        )
    
    async def _eval_record_exists(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        record_type = spec.expected.get("type", "")
        record_id = spec.expected.get("id", "")
        
        # Look for any observation that mentions this record
        all_obs = observations
        found = any(
            record_type in str(o.data) and (not record_id or record_id in str(o.data))
            for o in all_obs
        )
        
        return AssertionResult(
            assertion_type=spec.assertion_type, description=spec.description,
            passed=found, confidence=0.7 if found else 0.3,
            expected={"type": record_type, "id": record_id},
            message="Record found" if found else "Record not found in observations",
        )
    
    async def _eval_custom(
        self, spec: AssertionSpec, observations: list[ObservationRecord]
    ) -> AssertionResult:
        # Custom assertions check for key presence in observations
        key = spec.expected.get("key", "")
        value = spec.expected.get("value")
        
        for obs in observations:
            if key in obs.data:
                actual = obs.data[key]
                if value is None or actual == value:
                    return AssertionResult(
                        assertion_type=spec.assertion_type,
                        description=spec.description,
                        passed=True, confidence=0.9,
                        expected=spec.expected, actual={key: actual},
                        message="Custom assertion passed",
                    )
        
        return AssertionResult(
            assertion_type=spec.assertion_type,
            description=spec.description,
            passed=False, confidence=0.5,
            expected=spec.expected,
            message=f"Custom assertion failed: key '{key}' not found or value mismatch",
        )
