"""Confidence scoring and freshness decay for WebCMD memory.

Memory confidence = base_success_rate * recency * env_similarity * evidence_quality

Memory must never be trusted blindly. Every item has confidence,
freshness, and provenance. Stale items are treated as hints, not authority.
"""
from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field


class ConfidenceConfig(BaseModel):
    """Configuration for confidence scoring."""
    freshness_half_life_days: float = Field(default=14.0)
    min_confidence: float = Field(default=0.1)
    max_confidence: float = Field(default=0.99)
    evidence_weight: float = Field(default=0.2)
    recency_weight: float = Field(default=0.3)
    success_rate_weight: float = Field(default=0.5)


class ConfidenceEvaluator:
    """Evaluates and updates memory item confidence scores."""
    
    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self.config = config or ConfidenceConfig()
    
    def compute_freshness(self, last_verified: datetime | None) -> float:
        """Compute freshness factor using exponential decay.
        
        freshness = 2^(-age_days / half_life)
        
        Fresh (just verified) = 1.0
        After half_life days = 0.5
        Very old = approaches 0.0
        """
        if not last_verified:
            return 0.1  # Never verified = very low freshness
        
        now = datetime.now(timezone.utc)
        age = now - last_verified
        age_days = age.total_seconds() / 86400
        
        decay = math.pow(2, -age_days / self.config.freshness_half_life_days)
        return max(self.config.min_confidence, decay)
    
    def compute_success_rate(
        self, success_count: int, failure_count: int
    ) -> float:
        """Compute success rate with Bayesian smoothing.
        
        Uses Laplace smoothing to avoid 0/0 and 1/1 extremes.
        """
        total = success_count + failure_count
        if total == 0:
            return 0.5  # No data = neutral
        
        # Laplace smoothing with alpha=1
        return (success_count + 1) / (total + 2)
    
    def compute_evidence_quality(
        self, has_provenance: bool, observation_count: int
    ) -> float:
        """Score evidence quality."""
        if not has_provenance:
            return 0.3
        
        # More observations = higher quality, with diminishing returns
        quality = min(1.0, 0.5 + 0.1 * observation_count)
        return quality
    
    def compute_confidence(
        self,
        success_count: int = 0,
        failure_count: int = 0,
        last_verified: datetime | None = None,
        has_provenance: bool = True,
        observation_count: int = 1,
        env_similarity: float = 1.0,
    ) -> float:
        """Compute overall confidence score.
        
        confidence = success_rate * freshness * env_similarity * evidence_quality
        
        Bounded to [min_confidence, max_confidence]
        """
        success_rate = self.compute_success_rate(success_count, failure_count)
        freshness = self.compute_freshness(last_verified)
        evidence = self.compute_evidence_quality(has_provenance, observation_count)
        
        raw = (
            success_rate * self.config.success_rate_weight +
            freshness * self.config.recency_weight +
            evidence * self.config.evidence_weight
        ) * env_similarity
        
        return max(self.config.min_confidence, min(self.config.max_confidence, raw))
    
    def should_trust_directly(self, confidence: float) -> bool:
        """High confidence: use directly with standard verification."""
        return confidence >= 0.8
    
    def should_use_as_hint(self, confidence: float) -> bool:
        """Medium confidence: use as hint, verify aggressively."""
        return 0.4 <= confidence < 0.8
    
    def should_explore(self, confidence: float) -> bool:
        """Low confidence: require exploratory validation."""
        return confidence < 0.4
