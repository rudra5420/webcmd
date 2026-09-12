"""Worker registry for discovery and capability-based routing."""
from __future__ import annotations

import logging
from typing import Type

from webcmd.workers.base import BaseWorker
from webcmd.workers.types import CapabilitySet, PreparedAction, WorkerContext

logger = logging.getLogger(__name__)


class WorkerRegistry:
    """Manages worker registration, discovery, and capability matching.
    
    The registry is the bridge between the Execution Router and
    concrete worker implementations. It never exposes implementation
    details — only capabilities.
    """
    
    def __init__(self) -> None:
        self._worker_classes: dict[str, Type[BaseWorker]] = {}
        self._worker_instances: dict[str, BaseWorker] = {}
        self._capabilities_cache: dict[str, CapabilitySet] = {}
    
    def register(self, worker_class: Type[BaseWorker]) -> None:
        """Register a worker class by its type identifier."""
        # Create a temporary instance to get the type
        temp = worker_class.__new__(worker_class)
        worker_type = temp.worker_type
        self._worker_classes[worker_type] = worker_class
        logger.info(f"Registered worker: {worker_type}")
    
    async def get_worker(self, worker_type: str) -> BaseWorker:
        """Get or create a worker instance by type."""
        if worker_type not in self._worker_instances:
            if worker_type not in self._worker_classes:
                raise KeyError(f"No worker registered for type: {worker_type}")
            self._worker_instances[worker_type] = self._worker_classes[worker_type]()
        return self._worker_instances[worker_type]
    
    async def get_capabilities(self, worker_type: str) -> CapabilitySet:
        """Get cached capabilities for a worker type."""
        if worker_type not in self._capabilities_cache:
            worker = await self.get_worker(worker_type)
            self._capabilities_cache[worker_type] = await worker.capabilities()
        return self._capabilities_cache[worker_type]
    
    def find_workers_for_capability(self, capability_name: str) -> list[str]:
        """Find all worker types that support a given capability.
        
        Returns worker types ordered by registration order.
        The Execution Router uses this for routing decisions.
        """
        matches = []
        for worker_type, caps in self._capabilities_cache.items():
            if caps.has(capability_name):
                matches.append(worker_type)
        return matches
    
    async def find_best_worker(
        self,
        required_capabilities: list[str],
        preference_order: list[str] | None = None,
    ) -> str | None:
        """Find the best worker that supports ALL required capabilities.
        
        Args:
            required_capabilities: Capabilities the worker must support.
            preference_order: Preferred worker types (first = highest preference).
        
        Returns:
            Worker type string or None if no match found.
        """
        # Ensure all capabilities are cached
        for wt in self._worker_classes:
            if wt not in self._capabilities_cache:
                await self.get_capabilities(wt)
        
        # Find workers that support ALL required capabilities
        candidates = []
        for worker_type, caps in self._capabilities_cache.items():
            cap_names = caps.names()
            if all(req in cap_names for req in required_capabilities):
                candidates.append(worker_type)
        
        if not candidates:
            return None
        
        # Apply preference ordering
        if preference_order:
            for preferred in preference_order:
                if preferred in candidates:
                    return preferred
        
        return candidates[0]
    
    def list_registered(self) -> list[str]:
        """List all registered worker types."""
        return list(self._worker_classes.keys())
    
    async def shutdown_all(self) -> None:
        """Shutdown all active worker instances."""
        for worker_type, worker in self._worker_instances.items():
            try:
                await worker.shutdown()
                logger.info(f"Shut down worker: {worker_type}")
            except Exception as e:
                logger.error(f"Error shutting down {worker_type}: {e}")
        self._worker_instances.clear()
        self._capabilities_cache.clear()
