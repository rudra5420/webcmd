import uuid
from typing import Any
from webcmd.core.planner import Step

class WorkerRegistry:
    """
    Registry that keeps track of available workers and their capabilities.
    """
    def __init__(self):
        self.workers = {
            "api.http": ["api.get", "api.post", "api.put", "api.delete"],
            "browser.playwright": ["browser.navigate", "browser.click", "browser.type", "browser.read"],
            "browser.agentic": ["browser.agentic_explore"],
            "filesystem.local": ["filesystem.read", "filesystem.write", "filesystem.rename"],
            "shell.local": ["shell.run"]
        }

    def get_workers_for_capabilities(self, capabilities: list[str]) -> list[str]:
        matched = []
        for worker, caps in self.workers.items():
            if all(c in caps for c in capabilities):
                matched.append(worker)
        return matched

class ExecutionRouter:
    """
    Routes a Step to the most appropriate worker type.
    """
    def __init__(self):
        # Prefer deterministic workers
        self.preference_order = [
            "api.http",
            "filesystem.local",
            "shell.local",
            "browser.playwright",
            "browser.agentic"
        ]

    def route_step(self, step: Step, registry: WorkerRegistry, memory_hint: dict[str, Any] | None = None) -> str:
        """
        Examines step.required_capabilities, matches against available workers in WorkerRegistry,
        prefers deterministic workers over agentic exploration.
        """
        if memory_hint and "preferred_worker" in memory_hint:
            return memory_hint["preferred_worker"]
            
        matched_workers = registry.get_workers_for_capabilities(step.required_capabilities)
        if not matched_workers:
            # Fallback to agentic exploration if specific capabilities are not found
            if "browser.agentic_explore" in step.required_capabilities or not step.required_capabilities:
                return "browser.agentic"
            return "mock"
            
        # Sort by preference
        for pref in self.preference_order:
            if pref in matched_workers:
                return pref
                
        return matched_workers[0]
