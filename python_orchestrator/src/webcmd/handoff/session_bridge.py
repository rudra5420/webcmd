"""Session Bridge for secure credential exchange during handoffs.

When a browser worker discovers an API endpoint and hands off
to an API worker, session cookies or auth tokens need to transfer
without exposing raw secrets in the handoff payload.

The SessionBridge creates opaque session references backed by
the credential vault.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4
from webcmd.security.credentials import CredentialVault

logger = logging.getLogger(__name__)


class SessionBridge:
    """Manages secure session context transfer between workers."""
    
    def __init__(self, vault: CredentialVault | None = None) -> None:
        self.vault = vault or CredentialVault(service_name="webcmd_sessions")
        self._session_metadata: dict[str, dict[str, Any]] = {}
    
    def create_session_ref(
        self,
        session_data: dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> str:
        """Create an opaque session reference.
        
        Stores session data (cookies, tokens) in the vault
        and returns only an opaque reference key.
        """
        ref_key = f"session_{uuid4().hex[:16]}"
        
        # Store the actual session data securely
        self.vault.store(ref_key, json.dumps(session_data))
        
        # Store metadata (non-secret)
        self._session_metadata[ref_key] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(),
            "data_keys": list(session_data.keys()),
        }
        
        logger.info(f"Created session reference: {ref_key}")
        return ref_key
    
    def resolve_session_ref(self, ref_key: str) -> dict[str, Any] | None:
        """Resolve a session reference to actual session data.
        
        Only callable by authorized workers during handoff execution.
        Returns None if expired or not found.
        """
        # Check expiry
        meta = self._session_metadata.get(ref_key)
        if meta:
            expires = datetime.fromisoformat(meta["expires_at"])
            if datetime.now(timezone.utc) > expires:
                logger.warning(f"Session reference {ref_key} has expired")
                self.revoke_session_ref(ref_key)
                return None
        
        raw = self.vault.retrieve(ref_key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None
    
    def revoke_session_ref(self, ref_key: str) -> None:
        """Revoke a session reference."""
        self.vault.delete(ref_key)
        self._session_metadata.pop(ref_key, None)
        logger.info(f"Revoked session reference: {ref_key}")
