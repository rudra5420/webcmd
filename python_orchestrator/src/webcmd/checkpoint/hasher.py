"""Canonical JSON hashing for checkpoint integrity.

Uses deterministic JSON serialization (sorted keys, no whitespace)
followed by SHA-256 to produce tamper-detectable checkpoint hashes.
"""
import hashlib
import json
from typing import Any
from datetime import datetime
from uuid import UUID


class CanonicalHasher:
    """Produces deterministic SHA-256 hashes of checkpoint state."""
    
    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom serializer for types not natively JSON-serializable."""
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, set):
            return sorted(list(obj))
        if hasattr(obj, 'model_dump'):
            return obj.model_dump(mode='json')
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    
    @classmethod
    def canonical_json(cls, data: Any) -> str:
        """Produce canonical JSON string with sorted keys and no extra whitespace."""
        return json.dumps(
            data,
            sort_keys=True,
            separators=(',', ':'),
            default=cls._json_serializer,
            ensure_ascii=True,
        )
    
    @classmethod
    def compute_hash(cls, data: Any) -> str:
        """Compute SHA-256 hash of canonically serialized data."""
        canonical = cls.canonical_json(data)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    @classmethod
    def verify_hash(cls, data: Any, expected_hash: str) -> bool:
        """Verify a hash matches the canonical serialization of data."""
        return cls.compute_hash(data) == expected_hash
