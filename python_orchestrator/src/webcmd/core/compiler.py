import uuid
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from webcmd.core.planner import Step

class ObservationRecord(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    step_id: uuid.UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    worker_type: str
    action_taken: str
    result: Any
    is_success: bool
    context: dict[str, Any] = Field(default_factory=dict)

class WorkflowVersion(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    workflow_id: uuid.UUID
    version_number: int
    steps: list[Step]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Workflow(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    project_id: uuid.UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_version_id: uuid.UUID | None = None

class WorkflowCompiler:
    """
    Compiles a successful execution trace into a reusable Workflow and WorkflowVersion.
    """
    def compile_trace(
        self, 
        execution_id: uuid.UUID, 
        workflow_name: str, 
        steps: list[Step], 
        observations: list[ObservationRecord], 
        project_id: uuid.UUID
    ) -> tuple[Workflow, WorkflowVersion]:
        """
        Extracts stable element selectors that succeeded, parameterizes inputs,
        captures proven verification postconditions, and creates immutable 
        WorkflowVersion and Workflow.
        """
        workflow = Workflow(
            name=workflow_name,
            project_id=project_id
        )
        
        # In a real compiler, we would analyze the observations, parameterize the inputs,
        # and refine the steps. Here we simply take the executed steps and create a version.
        refined_steps = []
        for step in steps:
            # Simple parameterization mock
            refined_step = step.model_copy()
            if "url" in refined_step.action_spec:
                refined_step.action_spec["url_parameterized"] = True
            refined_steps.append(refined_step)
            
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version_number=1,
            steps=refined_steps
        )
        
        workflow.current_version_id = version.id
        return workflow, version
