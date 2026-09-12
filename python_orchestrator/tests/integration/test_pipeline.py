import pytest
import uuid
import asyncio
from webcmd.core.intent import IntentEngine, IntentSpec
from webcmd.core.planner import Planner, Step
from webcmd.core.router import ExecutionRouter, WorkerRegistry
from webcmd.core.compiler import WorkflowCompiler
from webcmd.workers.api.http_worker import HttpWorker
from webcmd.workers.types import PreparedAction, WorkerContext
from webcmd.state.enums import SideEffectStatus

@pytest.mark.asyncio
async def test_pipeline_end_to_end():
    # 1. Intent Engine
    intent_engine = IntentEngine()
    intent = intent_engine.normalize("Get data from https://jsonplaceholder.typicode.com/todos/1")
    
    assert intent.risk_level == "LOW"
    assert "https://jsonplaceholder.typicode.com/todos/1" in intent.target_urls

    # 2. Planner
    planner = Planner()
    steps = planner.plan(intent)
    assert len(steps) == 1
    step = steps[0]
    # Adjust step capability for test if it defaults to browser.navigate
    step.required_capabilities = ["api.get"]

    # 3. Execution Router & Worker Registry
    registry = WorkerRegistry()
    router = ExecutionRouter()
    worker_type = router.route_step(step, registry)
    assert worker_type == "api.http"

    # 4. Execution (Simulating Worker)
    worker = HttpWorker()
    context = WorkerContext(
        execution_id=uuid.uuid4(),
        step_id=step.id,
        worker_run_id=uuid.uuid4(),
        allowed_capabilities=["api.get"],
        time_budget_s=30.0
    )
    
    await worker.initialize(context)
    action = PreparedAction(
        worker_type="api.http",
        capability="api.get",
        target=step.action_spec.get("url")
    )
    
    prepared_action = await worker.prepare(action, context)
    result = await worker.execute(prepared_action, context)
    
    assert result.status == "succeeded"
    assert len(result.observations) > 0
    assert result.observations[0].observation_type == "http_response"

    await worker.shutdown()

    # 5. Compiler
    compiler = WorkflowCompiler()
    # Need observation records, we use what was emitted
    workflow, version = compiler.compile_trace(
        execution_id=context.execution_id,
        workflow_name="Fetch Todo",
        steps=steps,
        observations=result.observations,
        project_id=uuid.uuid4()
    )
    
    assert workflow.name == "Fetch Todo"
    assert version.workflow_id == workflow.id
    assert len(version.steps) == 1
    
    # We parameterize url in mock compiler
    assert version.steps[0].action_spec.get("url_parameterized") == True
