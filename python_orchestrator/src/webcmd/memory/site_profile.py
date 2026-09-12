"""Site profile manager for WebCMD.

Maintains per-domain operational records including
last visit, entrypoints, authentication status, and
environment fingerprints.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from webcmd.storage.database import DatabaseManager

logger = logging.getLogger(__name__)


class SiteProfileManager:
    """Manages per-domain site profiles."""
    
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
    
    async def get_or_create(
        self, project_id: UUID, domain: str
    ) -> dict[str, Any]:
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM site_profiles WHERE project_id = ? AND domain = ?",
                (str(project_id), domain),
            )
            row = await cursor.fetchone()
            
            if row:
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
            
            # Create new profile
            site_id = uuid4()
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                """
                INSERT INTO site_profiles (
                    site_id, project_id, domain, last_visit_at,
                    known_entrypoints, authentication_reference,
                    environment_fingerprint, profile_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(site_id), str(project_id), domain, now,
                 '[]', '', '{}', 1, now),
            )
            await conn.commit()
            
            return {
                "site_id": str(site_id),
                "domain": domain,
                "last_visit_at": now,
                "profile_version": 1,
            }
    
    async def update_visit(
        self, project_id: UUID, domain: str, url: str | None = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self.db.get_connection() as conn:
            await conn.execute(
                "UPDATE site_profiles SET last_visit_at = ?, last_success_at = ? WHERE project_id = ? AND domain = ?",
                (now, now, str(project_id), domain),
            )
            await conn.commit()
