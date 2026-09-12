"""SQLite-backed memory store for WebCMD.

Persists all 10 memory types with indexed queries
for fast retrieval by scope and type.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from webcmd.state.enums import MemoryType, MemoryStatus
from webcmd.storage.database import DatabaseManager

logger = logging.getLogger(__name__)


class MemoryStore:
    """Persistent memory storage backed by SQLite."""
    
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
    
    async def store(
        self,
        project_id: UUID,
        memory_type: MemoryType,
        scope_type: str,
        scope_key: str,
        content: dict[str, Any],
        provenance: dict[str, Any] | None = None,
        confidence: float = 0.5,
    ) -> UUID:
        """Store a new memory item."""
        memory_id = uuid4()
        now = datetime.now(timezone.utc).isoformat()
        
        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO memory_items (
                    memory_id, project_id, scope_type, scope_key,
                    memory_type, content, provenance, confidence,
                    freshness_score, last_verified_at,
                    success_count, failure_count, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(memory_id), str(project_id), scope_type, scope_key,
                    memory_type.value, json.dumps(content),
                    json.dumps(provenance or {}), confidence,
                    1.0, now, 0, 0, MemoryStatus.ACTIVE.value, now,
                ),
            )
            await conn.commit()
        
        return memory_id
    
    async def query(
        self,
        project_id: UUID,
        scope_type: str | None = None,
        scope_key: str | None = None,
        memory_type: MemoryType | None = None,
        min_confidence: float = 0.0,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        conditions = ["status = ?"]
        params: list[Any] = [status.value]
        if project_id:
            conditions.append("(project_id = ? OR project_id = '00000000-0000-0000-0000-000000000001')")
            params.append(str(project_id))
        
        if scope_type:
            conditions.append("scope_type = ?")
            params.append(scope_type)
        if scope_key:
            conditions.append("scope_key = ?")
            params.append(scope_key)
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)
        if min_confidence > 0:
            conditions.append("confidence >= ?")
            params.append(min_confidence)
        
        where = " AND ".join(conditions)
        params.append(limit)
        
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM memory_items WHERE {where} ORDER BY confidence DESC, created_at DESC LIMIT ?",
                params,
            )
            rows = await cursor.fetchall()
            columns = [d[0] for d in cursor.description]
            items = []
            for row in rows:
                item = dict(zip(columns, row))
                if isinstance(item.get("content"), str):
                    try:
                        item["content"] = json.loads(item["content"])
                    except Exception:
                        pass
                if isinstance(item.get("provenance"), str):
                    try:
                        item["provenance"] = json.loads(item["provenance"])
                    except Exception:
                        pass
                items.append(item)
            return items
    
    async def update_confidence(
        self, memory_id: UUID, new_confidence: float
    ) -> None:
        async with self.db.get_connection() as conn:
            await conn.execute(
                "UPDATE memory_items SET confidence = ? WHERE memory_id = ?",
                (new_confidence, str(memory_id)),
            )
            await conn.commit()
    
    async def record_success(self, memory_id: UUID) -> None:
        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE memory_items 
                SET success_count = success_count + 1,
                    last_verified_at = ?
                WHERE memory_id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), str(memory_id)),
            )
            await conn.commit()
    
    async def record_failure(self, memory_id: UUID) -> None:
        async with self.db.get_connection() as conn:
            await conn.execute(
                "UPDATE memory_items SET failure_count = failure_count + 1 WHERE memory_id = ?",
                (str(memory_id),),
            )
            await conn.commit()
    
    async def invalidate(
        self, memory_id: UUID, reason: str = ""
    ) -> None:
        """Soft invalidation - downgrade status, never delete."""
        async with self.db.get_connection() as conn:
            await conn.execute(
                "UPDATE memory_items SET status = ?, confidence = confidence * 0.5 WHERE memory_id = ?",
                (MemoryStatus.INVALIDATED.value, str(memory_id)),
            )
            await conn.commit()
        logger.info(f"Memory {memory_id} invalidated: {reason}")
