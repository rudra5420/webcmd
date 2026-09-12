"""Safe Resume Algorithm for WebCMD.

Never resumes blindly. The algorithm:
1. Load latest valid checkpoint
2. Verify integrity hash
3. Restore logical state
4. Probe external environment (ask workers to re-observe)
5. Check environment compatibility with checkpoint assumptions
6. If compatible: resume from checkpoint
7. If incompatible: flag for recovery or re-execution
"""
import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from webcmd.checkpoint.manager import CheckpointManager
from webcmd.checkpoint.models import CheckpointData, ResumeBoundary

logger = logging.getLogger(__name__)


class ResumeDecision(BaseModel):
    """Decision from the resume algorithm."""
    can_resume: bool
    checkpoint: CheckpointData | None = None
    resume_from_step_id: UUID | None = None
    environment_compatible: bool = True
    revalidation_needed: list[str] = Field(default_factory=list)
    uncertain_effects: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class ResumeCoordinator:
    """Coordinates safe execution resume from checkpoints."""
    
    def __init__(self, checkpoint_manager: CheckpointManager) -> None:
        self.checkpoint_manager = checkpoint_manager
    
    async def evaluate_resume(
        self,
        execution_id: UUID,
        current_environment: dict[str, Any] | None = None,
    ) -> ResumeDecision:
        """Evaluate whether an execution can safely resume.
        
        Steps:
        1. Load latest valid checkpoint
        2. Check integrity
        3. Compare environment state
        4. Determine resume point
        """
        # Step 1: Load checkpoint
        checkpoint = await self.checkpoint_manager.get_latest(execution_id)
        
        if not checkpoint:
            return ResumeDecision(
                can_resume=False,
                message="No valid checkpoint found for this execution",
            )
        
        # Step 2: Integrity already verified by CheckpointManager.get_latest()
        
        # Step 3: Check environment compatibility
        env_compatible = True
        revalidation_items = []
        
        if current_environment and checkpoint.environmental:
            # Check URL consistency
            if checkpoint.environmental.url and current_environment.get("url"):
                if checkpoint.environmental.url != current_environment.get("url"):
                    revalidation_items.append(
                        f"URL changed: {checkpoint.environmental.url} -> {current_environment.get('url')}"
                    )
            
            # Check session validity
            for ref in checkpoint.environmental.session_refs:
                if ref not in current_environment.get("active_sessions", []):
                    revalidation_items.append(f"Session may have expired: {ref}")
        
        # Step 4: Check for uncertain side effects
        uncertain = checkpoint.resume_boundary.uncertain_side_effects
        if uncertain:
            logger.warning(
                f"Checkpoint has {len(uncertain)} uncertain side effects - "
                f"environment probe required before resume"
            )
        
        # Step 5: Determine resume point
        resume_step = checkpoint.resume_boundary.next_step_id
        
        if not resume_step and checkpoint.logical.pending_steps:
            resume_step = checkpoint.logical.pending_steps[0]
        
        can_resume = resume_step is not None
        
        return ResumeDecision(
            can_resume=can_resume,
            checkpoint=checkpoint,
            resume_from_step_id=resume_step,
            environment_compatible=len(revalidation_items) == 0,
            revalidation_needed=revalidation_items,
            uncertain_effects=uncertain,
            message=(
                f"Safe to resume from step {resume_step}" if can_resume
                else "Cannot determine safe resume point"
            ),
        )
    
    async def confirm_resume(
        self,
        decision: ResumeDecision,
        environment_probed: bool = False,
    ) -> bool:
        """Confirm a resume decision after optional environment probing.
        
        If there are uncertain side effects and the environment
        hasn't been probed, refuse to resume.
        """
        if not decision.can_resume:
            return False
        
        if decision.uncertain_effects and not environment_probed:
            logger.warning(
                "Cannot confirm resume: uncertain side effects exist "
                "but environment has not been probed"
            )
            return False
        
        return True
