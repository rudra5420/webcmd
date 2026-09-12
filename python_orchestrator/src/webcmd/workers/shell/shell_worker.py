import asyncio
import shlex
import uuid
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

class ShellWorker(BaseWorker):
    """
    Shell worker for executing system commands.
    """
    
    def __init__(self, allowed_commands: Optional[List[str]] = None, default_timeout: float = 60.0):
        self.allowed_commands = allowed_commands
        self.default_timeout = default_timeout

    @property
    def worker_type(self) -> str:
        return "shell.local"

    @property
    def worker_name(self) -> str:
        return "Local Shell Worker"
        
    async def initialize(self, context: WorkerContext) -> None:
        pass

    async def capabilities(self) -> CapabilitySet:
        caps = [
            Capability(name="shell.execute", description="", idempotency=IdempotencyType.NON_IDEMPOTENT, risk_level=RiskLevel.HIGH),
        ]
        return CapabilitySet(capabilities=caps)

    async def prepare(self, action: PreparedAction, context: WorkerContext) -> PreparedAction:
        return action

    def _is_command_allowed(self, cmd: str) -> bool:
        if self.allowed_commands is None:
            return True
            
        args = shlex.split(cmd)
        if not args:
            return False
            
        base_cmd = args[0]
        return base_cmd in self.allowed_commands

    async def execute(self, action: PreparedAction, context: WorkerContext) -> WorkerResult:
        if action.capability != "shell.execute":
            raise PermanentError(f"Unsupported capability: {action.capability}")
            
        command = action.parameters.get("command") or action.target
        if not command:
            raise PermanentError("Command payload is missing")
            
        if not self._is_command_allowed(command):
            raise PermanentError(f"Command not allowed: {command}")
            
        timeout = action.parameters.get("timeout", self.default_timeout)
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
            
            stdout = stdout_bytes.decode(errors='replace')
            stderr = stderr_bytes.decode(errors='replace')
            return_code = process.returncode
            
            obs = ObservationRecord(
                observation_type="shell_output",
                data={
                    "command": command,
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": return_code
                },
                trust_class=TrustLevel.T4_TOOL_OUTPUT
            )
            
            return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)
            
        except asyncio.TimeoutError as e:
            # Kill process if it timed out
            try:
                process.kill()
            except Exception:
                pass
            raise TransientError(f"Command timed out after {timeout} seconds") from e
        except Exception as e:
            raise WorkerError(f"Shell execution failed: {e}") from e

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
