# WebCMD — Data Model

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Modeling Rules

The data model distinguishes user intent, reusable workflow definition, a concrete execution, worker activity, runtime state and evidence. No concept may be overloaded merely because several have similar fields.

## 2. Core Entities

### Project
Top-level namespace for workflows, runs, policies, memory and artifacts.

Key fields:
- `project_id`
- `name`
- `description`
- `owner_id`
- `config`
- `created_at`
- `updated_at`

### IntentSpec
Normalized representation of a user request.

Fields:
- `intent_id`
- `project_id`
- `original_text`
- `objective`
- `constraints`
- `inputs`
- `desired_outputs`
- `risk_level`
- `created_at`

### Task
A requested unit of work. A task may be executed more than once.

Fields:
- `task_id`
- `intent_id`
- `project_id`
- `status`
- `priority`
- `created_at`

### Workflow
Reusable procedure for accomplishing a class of tasks.

Fields:
- `workflow_id`
- `project_id`
- `name`
- `description`
- `status`
- `active_version_id`
- `created_at`

### WorkflowVersion
Immutable version of a workflow.

Fields:
- `workflow_version_id`
- `workflow_id`
- `version`
- `steps`
- `inputs_schema`
- `outputs_schema`
- `preconditions`
- `postconditions`
- `risk_profile`
- `source_execution_id`
- `confidence`
- `created_at`

A version is immutable. Corrections create a new version.

### Step
A logical workflow unit.

Fields:
- `step_id`
- `workflow_version_id`
- `sequence`
- `name`
- `objective`
- `required_capabilities`
- `action_spec`
- `preconditions`
- `verification_spec`
- `retry_policy`
- `risk_level`

### Execution
One concrete attempt to satisfy a task/workflow.

Fields:
- `execution_id`
- `task_id`
- `workflow_version_id`
- `status`
- `current_step_id`
- `current_worker_run_id`
- `started_at`
- `finished_at`
- `result`
- `failure_code`

### Worker
Registered execution implementation.

Fields:
- `worker_id`
- `type`
- `name`
- `version`
- `capabilities`
- `trust_level`
- `configuration_reference`

### WorkerRun
One worker's participation in an execution.

Fields:
- `worker_run_id`
- `execution_id`
- `worker_id`
- `step_id`
- `status`
- `attempt_number`
- `started_at`
- `finished_at`
- `result`
- `failure_code`

### Observation
Raw or normalized evidence observed during execution.

Fields:
- `observation_id`
- `execution_id`
- `worker_run_id`
- `type`
- `payload_reference`
- `captured_at`
- `trust_class`

### Assertion
Expected condition evaluated against observations.

Fields:
- `assertion_id`
- `execution_id`
- `step_id`
- `expression`
- `result`
- `evidence_references`
- `evaluated_at`

### Checkpoint
Resumable state snapshot with evidence references.

Fields:
- `checkpoint_id`
- `execution_id`
- `sequence_number`
- `state_hash`
- `logical_state`
- `environment_state`
- `resume_boundary`
- `verification_status`
- `created_at`

### Handoff
Transfer of execution responsibility between workers or agents.

Fields:
- `handoff_id`
- `execution_id`
- `source_worker_run_id`
- `target_worker_id`
- `payload_reference`
- `reason`
- `status`
- `created_at`

### RecoveryAttempt
A bounded attempt to restore progress after a failure.

Fields:
- `recovery_id`
- `execution_id`
- `trigger_failure_code`
- `strategy`
- `attempt_number`
- `result`
- `evidence_references`
- `created_at`

### Artifact
Produced or captured file/object.

Fields:
- `artifact_id`
- `execution_id`
- `kind`
- `path_or_uri`
- `content_hash`
- `metadata`
- `created_at`

### MemoryItem
Persistent learning record.

Fields:
- `memory_id`
- `project_id`
- `scope_type`
- `scope_key`
- `memory_type`
- `content`
- `provenance`
- `confidence`
- `freshness_score`
- `last_verified_at`
- `success_count`
- `failure_count`
- `status`

### SiteProfile
Aggregated state for a site/domain.

Fields:
- `site_id`
- `project_id`
- `domain`
- `last_visit_at`
- `last_success_at`
- `known_entrypoints`
- `authentication_reference`
- `environment_fingerprint`
- `profile_version`

### Policy
Machine-enforceable capability and risk policy.

Fields:
- `policy_id`
- `project_id`
- `rules`
- `version`
- `created_at`

### Approval
Explicit user approval for a gated action.

Fields:
- `approval_id`
- `execution_id`
- `scope`
- `requested_action`
- `decision`
- `approved_by`
- `expires_at`

## 3. Relationships

```text
Project
 ├── IntentSpec → Task → Execution
 ├── Workflow → WorkflowVersion → Step
 ├── Worker → WorkerRun
 ├── Policy → Approval
 ├── SiteProfile → MemoryItem
 └── Artifacts / Audit Events
```

An `Execution` references a concrete `WorkflowVersion`, allowing historical runs to remain interpretable after new versions are created.

## 4. Immutability Rules

Immutable after creation:
- WorkflowVersion
- Execution event records
- Observation records
- Assertions
- Checkpoints
- RecoveryAttempt records
- Handoff records

Mutable aggregate projections may be updated for performance, but can always be reconstructed from immutable event history.

## 5. IDs and Versioning

Use opaque, globally unique IDs (UUID/ULID). Use monotonic sequence numbers where event ordering matters.

## 6. Sensitive Data Rules

Raw passwords, cookies, OAuth refresh tokens, API secrets, OTPs and payment secrets do not belong in ordinary entities. Store secure references and access metadata only.

## 7. Indexing Priorities

Indexes should exist for:
- `Execution(project_id, status)`
- `Execution(task_id)`
- `WorkerRun(execution_id, sequence)`
- `Checkpoint(execution_id, sequence_number)`
- `MemoryItem(scope_type, scope_key, memory_type)`
- `Workflow(name, project_id)`
- `WorkflowVersion(workflow_id, version)`
- `AuditEvent(execution_id, sequence)`

## 8. Model Invariants

1. An execution must reference a valid task.
2. A worker run cannot outlive its execution.
3. A completed execution must have a terminal verification/result state.
4. A workflow version cannot be modified in place.
5. A checkpoint must reference a reproducible state boundary.
6. A successful memory promotion must reference execution evidence.
7. An approval must be bound to a specific action scope and expiry.
