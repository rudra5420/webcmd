"""Checkpoint manager for WebCMD.

Handles atomic creation, validation, retrieval, and pruning of
execution checkpoints.

Atomicity: Uses temp file -> fsync -> rename pattern to prevent
corrupted checkpoints from process crashes.
"""
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from webcmd.checkpoint.hasher import CanonicalHasher
from webcmd.checkpoint.models import (
    CheckpointData,
    CheckpointTrigger,
    EnvironmentalCheckpoint,
    EvidenceCheckpoint,
    LogicalCheckpoint,
    RecoveryCheckpoint,
    ResumeBoundary,
)
from webcmd.config import WebCMDConfig

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoint lifecycle."""
    
    def __init__(self, config: WebCMDConfig) -> None:
        self.config = config
        self._checkpoints_dir = config.home_dir / "checkpoints"
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._sequence_counters: dict[UUID, int] = {}
    
    def _get_execution_dir(self, execution_id: UUID) -> Path:
        d = self._checkpoints_dir / str(execution_id)
        d.mkdir(parents=True, exist_ok=True)
        return d
    
    def _next_sequence(self, execution_id: UUID) -> int:
        current = self._sequence_counters.get(execution_id, 0)
        self._sequence_counters[execution_id] = current + 1
        return current + 1
    
    async def create(
        self,
        execution_id: UUID,
        trigger: CheckpointTrigger,
        logical: LogicalCheckpoint | None = None,
        environmental: EnvironmentalCheckpoint | None = None,
        evidence: EvidenceCheckpoint | None = None,
        recovery_state: RecoveryCheckpoint | None = None,
        resume_boundary: ResumeBoundary | None = None,
    ) -> CheckpointData:
        """Create an atomic checkpoint.
        
        Uses temp-file + fsync + rename for crash safety.
        """
        seq = self._next_sequence(execution_id)
        
        checkpoint = CheckpointData(
            execution_id=execution_id,
            sequence_number=seq,
            trigger=trigger,
            logical=logical or LogicalCheckpoint(),
            environmental=environmental or EnvironmentalCheckpoint(),
            evidence=evidence or EvidenceCheckpoint(),
            recovery=recovery_state or RecoveryCheckpoint(),
            resume_boundary=resume_boundary or ResumeBoundary(),
        )
        
        # Compute integrity hash over logical + evidence state
        hash_data = {
            "logical": checkpoint.logical.model_dump(mode='json'),
            "evidence": checkpoint.evidence.model_dump(mode='json'),
            "sequence": seq,
        }
        checkpoint.state_hash = CanonicalHasher.compute_hash(hash_data)
        
        # Atomic write: temp file -> fsync -> rename
        exec_dir = self._get_execution_dir(execution_id)
        final_path = exec_dir / f"checkpoint_{seq:04d}.json"
        
        data_json = checkpoint.model_dump_json(indent=2)
        
        # Write to temp file in same directory (for same-filesystem rename)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(exec_dir),
            prefix=".checkpoint_tmp_",
            suffix=".json",
        )
        try:
            os.write(fd, data_json.encode('utf-8'))
            os.fsync(fd)
            os.close(fd)
            
            # Atomic rename
            os.replace(tmp_path, str(final_path))
            
            logger.info(
                f"Checkpoint created: execution={execution_id}, "
                f"seq={seq}, trigger={trigger}, hash={checkpoint.state_hash[:12]}"
            )
        except Exception:
            os.close(fd) if not os._exists else None
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        
        return checkpoint
    
    async def get_latest(
        self, execution_id: UUID
    ) -> CheckpointData | None:
        """Get the most recent valid checkpoint for an execution."""
        exec_dir = self._get_execution_dir(execution_id)
        
        checkpoint_files = sorted(
            exec_dir.glob("checkpoint_*.json"),
            key=lambda p: p.name,
            reverse=True,
        )
        
        for cp_file in checkpoint_files:
            try:
                data = json.loads(cp_file.read_text(encoding='utf-8'))
                checkpoint = CheckpointData.model_validate(data)
                
                # Verify integrity hash
                if checkpoint.state_hash:
                    hash_data = {
                        "logical": checkpoint.logical.model_dump(mode='json'),
                        "evidence": checkpoint.evidence.model_dump(mode='json'),
                        "sequence": checkpoint.sequence_number,
                    }
                    if not CanonicalHasher.verify_hash(hash_data, checkpoint.state_hash):
                        logger.warning(f"Checkpoint integrity check failed: {cp_file}")
                        continue
                
                return checkpoint
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {cp_file}: {e}")
                continue
        
        return None
    
    async def get_all(
        self, execution_id: UUID
    ) -> list[CheckpointData]:
        """Get all checkpoints for an execution, ordered by sequence."""
        exec_dir = self._get_execution_dir(execution_id)
        results = []
        
        for cp_file in sorted(exec_dir.glob("checkpoint_*.json")):
            try:
                data = json.loads(cp_file.read_text(encoding='utf-8'))
                checkpoint = CheckpointData.model_validate(data)
                results.append(checkpoint)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {cp_file}: {e}")
        
        return results
    
    async def prune(
        self,
        execution_id: UUID,
        keep_last_n: int = 3,
        keep_triggers: set[CheckpointTrigger] | None = None,
    ) -> int:
        """Prune old checkpoints, keeping recent and important ones.
        
        Always keeps:
        - Last N checkpoints
        - All pre_risk and shutdown checkpoints
        
        Returns number of pruned checkpoints.
        """
        keep_triggers = keep_triggers or {
            CheckpointTrigger.PRE_RISK,
            CheckpointTrigger.SHUTDOWN,
            CheckpointTrigger.PRE_HUMAN_VERIFICATION,
        }
        
        all_checkpoints = await self.get_all(execution_id)
        if len(all_checkpoints) <= keep_last_n:
            return 0
        
        # Determine which to keep
        to_keep = set()
        # Keep last N
        for cp in all_checkpoints[-keep_last_n:]:
            to_keep.add(cp.checkpoint_id)
        # Keep important triggers
        for cp in all_checkpoints:
            if cp.trigger in keep_triggers:
                to_keep.add(cp.checkpoint_id)
        
        # Delete the rest
        pruned = 0
        exec_dir = self._get_execution_dir(execution_id)
        for cp in all_checkpoints:
            if cp.checkpoint_id not in to_keep:
                cp_file = exec_dir / f"checkpoint_{cp.sequence_number:04d}.json"
                if cp_file.exists():
                    cp_file.unlink()
                    pruned += 1
        
        logger.info(f"Pruned {pruned} checkpoints for execution {execution_id}")
        return pruned
