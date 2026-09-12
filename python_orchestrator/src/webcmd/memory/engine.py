"""WebCMD Memory Engine.

Coordinates the entire memory subsystem: storage, retrieval,
confidence scoring, and learning from execution traces.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from webcmd.memory.confidence import ConfidenceEvaluator
from webcmd.memory.retrieval import HierarchicalRetriever, RetrievalResult
from webcmd.memory.store import MemoryStore
from webcmd.state.enums import MemoryType
from webcmd.storage.database import DatabaseManager

logger = logging.getLogger(__name__)


class MemoryEngine:
    """Coordinates memory storage, retrieval, and learning."""
    
    def __init__(self, db: DatabaseManager) -> None:
        self.store = MemoryStore(db)
        self.evaluator = ConfidenceEvaluator()
        self.retriever = HierarchicalRetriever(self.store, self.evaluator)
    
    async def remember_site(
        self,
        project_id: UUID,
        domain: str,
        data: dict[str, Any],
        execution_id: UUID | None = None,
        confidence: float = 0.7,
    ) -> UUID:
        """Store site-level memory."""
        provenance = {"execution_id": str(execution_id)} if execution_id else {}
        return await self.store.store(
            project_id=project_id,
            memory_type=MemoryType.SITE,
            scope_type="site",
            scope_key=domain,
            content=data,
            provenance=provenance,
            confidence=confidence,
        )
    
    async def remember_interaction(
        self,
        project_id: UUID,
        page_url: str,
        element: str,
        successful_strategy: str,
        selector: str,
        execution_id: UUID | None = None,
        confidence: float = 0.8,
    ) -> UUID:
        """Store interaction memory (which locator strategy worked)."""
        return await self.store.store(
            project_id=project_id,
            memory_type=MemoryType.INTERACTION,
            scope_type="page",
            scope_key=page_url,
            content={
                "element": element,
                "strategy": successful_strategy,
                "selector": selector,
            },
            provenance={"execution_id": str(execution_id)} if execution_id else {},
            confidence=confidence,
        )
    
    async def remember_failure_recovery(
        self,
        project_id: UUID,
        domain: str,
        failure_type: str,
        repair_action: str,
        success: bool,
        execution_id: UUID | None = None,
        confidence: float | None = None,
    ) -> UUID:
        """Store a failure recovery outcome."""
        if confidence is None:
            confidence = 0.8 if success else 0.3
        return await self.store.store(
            project_id=project_id,
            memory_type=MemoryType.RECOVERY,
            scope_type="site",
            scope_key=domain,
            content={
                "failure_type": failure_type,
                "repair_action": repair_action,
                "success": success,
            },
            provenance={"execution_id": str(execution_id)} if execution_id else {},
            confidence=confidence,
        )
    
    async def remember_last_known_state(
        self,
        project_id: UUID,
        domain: str,
        state: dict[str, Any],
    ) -> UUID:
        """Store last-known-state for a site."""
        return await self.store.store(
            project_id=project_id,
            memory_type=MemoryType.LAST_KNOWN_STATE,
            scope_type="site",
            scope_key=domain,
            content=state,
            confidence=0.9,
        )
    
    async def recall(
        self,
        project_id: UUID,
        domain: str | None = None,
        workflow_name: str | None = None,
        page_url: str | None = None,
    ) -> RetrievalResult:
        """Recall relevant memory using the hierarchical cascade."""
        return await self.retriever.cascade_retrieve(
            project_id=project_id,
            domain=domain,
            workflow_name=workflow_name,
            page_url=page_url,
        )
    
    async def learn_from_execution(
        self,
        project_id: UUID,
        execution_id: UUID,
        domain: str | None = None,
        url: str | None = None,
        successful_steps: list[dict[str, Any]] | None = None,
        failed_steps: list[dict[str, Any]] | None = None,
        human_verified: bool = False,
        human_rejected: bool = False,
        human_reason: str | None = None,
    ) -> None:
        """Extract and store learning from an execution with human verification distinction.
        
        - Human-confirmed success: Strong positive signal (confidence 0.95).
        - Automated-only success: Standard baseline signal (confidence 0.70).
        - Human rejection: Negative signal in failure memory; does not strengthen workflow.
        """
        if human_rejected:
            if domain:
                await self.store.store(
                    project_id=project_id,
                    memory_type=MemoryType.FAILURE,
                    scope_type="site",
                    scope_key=domain,
                    content={
                        "human_rejected": True,
                        "rejection_reason": human_reason or "User rejected final result",
                        "last_execution": str(execution_id),
                    },
                    provenance={
                        "execution_id": str(execution_id),
                        "human_verified": False,
                        "human_rejected": True,
                    },
                    confidence=0.2,
                )
            logger.info(f"Recorded human rejection for execution {execution_id}. Workflow not strengthened.")
            return

        confidence = 0.95 if human_verified else 0.70
        provenance = {
            "execution_id": str(execution_id),
            "human_verified": human_verified,
            "verification_type": "human_confirmed" if human_verified else "automated_only",
        }

        if domain:
            await self.store.store(
                project_id=project_id,
                memory_type=MemoryType.SITE,
                scope_type="site",
                scope_key=domain,
                content={
                    "last_url": url,
                    "last_execution": str(execution_id),
                    "human_confirmed": human_verified,
                },
                provenance=provenance,
                confidence=confidence,
            )
        
        for step in (successful_steps or []):
            if step.get("locator_strategy") and url:
                await self.store.store(
                    project_id=project_id,
                    memory_type=MemoryType.INTERACTION,
                    scope_type="page",
                    scope_key=url,
                    content={
                        "element": step.get("element", ""),
                        "strategy": step["locator_strategy"],
                        "selector": step.get("selector", ""),
                        "human_confirmed": human_verified,
                    },
                    provenance=provenance,
                    confidence=confidence,
                )
        
        logger.info(f"Learned from execution {execution_id} (human_verified={human_verified}, confidence={confidence})")
