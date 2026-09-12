import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from webcmd.workers.base import (
    BaseWorker,
    WorkerError,
    TransientError,
    PermanentError,
    StateMismatchError
)
from webcmd.workers.types import (
    Capability,
    CapabilitySet,
    WorkerContext,
    PreparedAction,
    WorkerResult,
    ObservationRecord,
    PauseResult,
    ResumeResult,
    IdempotencyType,
    RiskLevel,
    SideEffectStatus,
    TrustLevel
)

class FilesystemWorker(BaseWorker):
    """
    Filesystem worker for performing file operations.
    """
    
    @property
    def worker_type(self) -> str:
        return "filesystem.local"

    @property
    def worker_name(self) -> str:
        return "Local Filesystem Worker"
        
    async def initialize(self, context: WorkerContext) -> None:
        pass

    async def capabilities(self) -> CapabilitySet:
        caps = [
            Capability(name="filesystem.read", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
            Capability(name="filesystem.write", description="", idempotency=IdempotencyType.NON_IDEMPOTENT, risk_level=RiskLevel.MEDIUM),
            Capability(name="filesystem.rename", description="", idempotency=IdempotencyType.NON_IDEMPOTENT, risk_level=RiskLevel.MEDIUM),
            Capability(name="filesystem.delete", description="", idempotency=IdempotencyType.NON_IDEMPOTENT, risk_level=RiskLevel.HIGH),
            Capability(name="filesystem.list", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
            Capability(name="filesystem.exists", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
        ]
        return CapabilitySet(capabilities=caps)

    async def prepare(self, action: PreparedAction, context: WorkerContext) -> PreparedAction:
        return action

    def _get_file_metadata(self, path: Path) -> Dict[str, Any]:
        """Get size, hash, and modification time for a file."""
        if not path.is_file():
            return {}
        
        stat = path.stat()
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                
        return {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "hash_sha256": sha256_hash.hexdigest()
        }

    async def execute(self, action: PreparedAction, context: WorkerContext) -> WorkerResult:
        try:
            if action.capability == "filesystem.read":
                return await self._execute_read(action)
            elif action.capability == "filesystem.write":
                return await self._execute_write(action)
            elif action.capability == "filesystem.rename":
                return await self._execute_rename(action)
            elif action.capability == "filesystem.delete":
                return await self._execute_delete(action)
            elif action.capability == "filesystem.list":
                return await self._execute_list(action)
            elif action.capability == "filesystem.exists":
                return await self._execute_exists(action)
            else:
                raise PermanentError(f"Unsupported capability: {action.capability}")
        except FileNotFoundError as e:
            raise PermanentError(f"File not found: {e}") from e
        except PermissionError as e:
            raise PermanentError(f"Permission denied: {e}") from e
        except OSError as e:
            raise WorkerError(f"OS error: {e}") from e

    async def _execute_read(self, action: PreparedAction) -> WorkerResult:
        raw_path = action.target or action.parameters.get("path")
        if not raw_path:
            raise PermanentError("Path is required")
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
            
        content = path.read_text(encoding="utf-8")
        metadata = self._get_file_metadata(path)
        
        obs = ObservationRecord(
            observation_type="file_state",
            data={"content": content, "metadata": metadata, "path": str(path)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.NO_EFFECT)

    async def _execute_write(self, action: PreparedAction) -> WorkerResult:
        raw_path = action.target or action.parameters.get("path")
        if not raw_path:
            raise PermanentError("Path is required")
        path = Path(raw_path)
        content = action.parameters.get("content", "")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        metadata = self._get_file_metadata(path)
        
        obs = ObservationRecord(
            observation_type="file_state",
            data={"metadata": metadata, "path": str(path)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)

    async def _execute_rename(self, action: PreparedAction) -> WorkerResult:
        src = action.target or action.parameters.get("src")
        dst = action.parameters.get("dst")
        if not src or not dst:
            raise PermanentError("Source and destination paths are required")
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {src_path}")
            
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        
        obs = ObservationRecord(
            observation_type="file_state",
            data={"renamed_from": str(src_path), "path": str(dst_path)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)

    async def _execute_delete(self, action: PreparedAction) -> WorkerResult:
        raw_path = action.target or action.parameters.get("path")
        if not raw_path:
            raise PermanentError("Path is required")
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
            
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
            
        obs = ObservationRecord(
            observation_type="file_state",
            data={"deleted": True, "path": str(path)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)

    async def _execute_list(self, action: PreparedAction) -> WorkerResult:
        raw_path = action.target or action.parameters.get("path")
        if not raw_path:
            raise PermanentError("Path is required")
        path = Path(raw_path)
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Directory not found: {path}")
            
        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0
            })
            
        obs = ObservationRecord(
            observation_type="file_state",
            data={"items": items, "path": str(path)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.NO_EFFECT)

    async def _execute_exists(self, action: PreparedAction) -> WorkerResult:
        raw_path = action.target or action.parameters.get("path")
        if not raw_path:
            raise PermanentError("Path is required")
        path = Path(raw_path)
        exists = path.exists()
        
        obs = ObservationRecord(
            observation_type="file_state",
            data={"exists": exists, "path": str(path)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.NO_EFFECT)

    async def observe(self, context: WorkerContext) -> List[ObservationRecord]:
        return []

    async def pause(self) -> PauseResult:
        return PauseResult(success=True, state_snapshot={})

    async def resume(self, context: WorkerContext) -> ResumeResult:
        return ResumeResult(success=True)

    async def cancel(self, reason: str) -> None:
        pass

    async def shutdown(self) -> None:
        pass
