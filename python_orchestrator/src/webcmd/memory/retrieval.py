"""Hierarchical memory retrieval for WebCMD.

Retrieval cascade (vector-free core):
    Exact site/workflow match -> Exact page/action match -> Related pattern -> New exploration

No vector database required for core correctness.
"""
from __future__ import annotations
import logging
from typing import Any
from uuid import UUID
from webcmd.state.enums import MemoryType, MemoryStatus
from webcmd.memory.store import MemoryStore
from webcmd.memory.confidence import ConfidenceEvaluator

logger = logging.getLogger(__name__)


class RetrievalResult:
    """Result of a memory retrieval."""
    def __init__(
        self,
        found: bool,
        items: list[dict[str, Any]] | None = None,
        source: str = "",
        confidence: float = 0.0,
    ):
        self.found = found
        self.items = items or []
        self.source = source
        self.confidence = confidence


class HierarchicalRetriever:
    """Retrieves memory using a deterministic cascade."""
    
    def __init__(
        self,
        store: MemoryStore,
        evaluator: ConfidenceEvaluator | None = None,
    ) -> None:
        self.store = store
        self.evaluator = evaluator or ConfidenceEvaluator()
    
    async def retrieve_for_site(
        self,
        project_id: UUID,
        domain: str,
        min_confidence: float = 0.3,
    ) -> RetrievalResult:
        """Retrieve site-level memory."""
        items = await self.store.query(
            project_id=project_id,
            scope_type="site",
            scope_key=domain,
            memory_type=MemoryType.SITE,
            min_confidence=min_confidence,
        )
        return RetrievalResult(
            found=len(items) > 0,
            items=items,
            source="site_memory",
            confidence=items[0]["confidence"] if items else 0.0,
        )
    
    async def retrieve_for_workflow(
        self,
        project_id: UUID,
        workflow_name: str,
        min_confidence: float = 0.3,
    ) -> RetrievalResult:
        """Retrieve workflow-level memory."""
        items = await self.store.query(
            project_id=project_id,
            scope_type="workflow",
            scope_key=workflow_name,
            memory_type=MemoryType.WORKFLOW,
            min_confidence=min_confidence,
        )
        return RetrievalResult(
            found=len(items) > 0,
            items=items,
            source="workflow_memory",
            confidence=items[0]["confidence"] if items else 0.0,
        )
    
    async def retrieve_interaction(
        self,
        project_id: UUID,
        page_url: str,
        element_description: str = "",
        min_confidence: float = 0.3,
    ) -> RetrievalResult:
        """Retrieve interaction-level memory (locator strategies, etc.)."""
        items = await self.store.query(
            project_id=project_id,
            scope_type="page",
            scope_key=page_url,
            memory_type=MemoryType.INTERACTION,
            min_confidence=min_confidence,
        )
        return RetrievalResult(
            found=len(items) > 0,
            items=items,
            source="interaction_memory",
            confidence=items[0]["confidence"] if items else 0.0,
        )
    
    async def retrieve_failure_recovery(
        self,
        project_id: UUID,
        domain: str,
        failure_type: str = "",
    ) -> RetrievalResult:
        """Retrieve known recovery strategies for a domain."""
        items = await self.store.query(
            project_id=project_id,
            scope_type="site",
            scope_key=domain,
            memory_type=MemoryType.RECOVERY,
        )
        return RetrievalResult(
            found=len(items) > 0,
            items=items,
            source="recovery_memory",
            confidence=items[0]["confidence"] if items else 0.0,
        )
    
    async def cascade_retrieve(
        self,
        project_id: UUID,
        domain: str | None = None,
        workflow_name: str | None = None,
        page_url: str | None = None,
        min_confidence: float = 0.3,
    ) -> RetrievalResult:
        """Execute the full retrieval cascade.
        
        Order:
        1. Exact workflow match
        2. Exact site match
        3. Page/interaction match
        4. Fall through to exploration
        """
        # Level 1: Exact workflow
        if workflow_name:
            result = await self.retrieve_for_workflow(project_id, workflow_name, min_confidence)
            if result.found:
                logger.info(f"Cascade hit: workflow '{workflow_name}' (confidence={result.confidence:.2f})")
                return result
        
        # Level 2: Site memory
        if domain:
            result = await self.retrieve_for_site(project_id, domain, min_confidence)
            if result.found:
                logger.info(f"Cascade hit: site '{domain}' (confidence={result.confidence:.2f})")
                return result
        
        # Level 3: Page/interaction
        if page_url:
            result = await self.retrieve_interaction(project_id, page_url, min_confidence=min_confidence)
            if result.found:
                logger.info(f"Cascade hit: page '{page_url}' (confidence={result.confidence:.2f})")
                return result
        
        # Level 4: No match - exploration needed
        logger.info("Cascade miss: no relevant memory found, exploration needed")
        return RetrievalResult(
            found=False,
            source="none",
            confidence=0.0,
        )
