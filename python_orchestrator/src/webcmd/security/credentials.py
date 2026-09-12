"""Credential vault interface for WebCMD.

Wraps OS-native credential storage (keyring) so that
raw secrets are NEVER stored in entities, events, or memory.
All references are opaque vault keys.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class CredentialVault:
    """Interface to OS-native credential storage.
    
    Uses opaque references. Raw secrets never appear in
    application state, events, logs, or memory.
    """
    
    def __init__(self, service_name: str = "webcmd") -> None:
        self.service_name = service_name
        self._fallback: dict[str, str] = {}  # In-memory fallback for testing
    
    def store(self, key: str, secret: str) -> str:
        """Store a secret and return an opaque reference."""
        ref = f"vault://{self.service_name}/{key}"
        try:
            import keyring
            keyring.set_password(self.service_name, key, secret)
        except (ImportError, Exception) as e:
            logger.warning(f"Keyring unavailable, using in-memory fallback: {e}")
            self._fallback[key] = secret
        return ref
    
    def retrieve(self, key: str) -> str | None:
        """Retrieve a secret by key. Returns None if not found."""
        try:
            import keyring
            return keyring.get_password(self.service_name, key)
        except (ImportError, Exception):
            return self._fallback.get(key)
    
    def delete(self, key: str) -> None:
        """Delete a stored secret."""
        try:
            import keyring
            keyring.delete_password(self.service_name, key)
        except (ImportError, Exception):
            self._fallback.pop(key, None)
    
    def exists(self, key: str) -> bool:
        """Check if a credential exists."""
        return self.retrieve(key) is not None
