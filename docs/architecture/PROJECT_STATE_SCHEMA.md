# WebCMD — Project State Schema

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Purpose

This schema defines canonical runtime truth: what the system believes is happening now, what has completed, what remains, what evidence exists, and where execution can resume.

## 2. State Principles

- State transitions are explicit.
- Terminal state cannot be silently reverted.
- Every execution step has a status.
- Logical state and environmental state are distinct.
- Unknown is a valid state.
- A model's text is not authoritative state.

## 3. Top-Level Schema

```yaml
project_state:
  project_id: string
  project_status: ACTIVE | PAUSED | ERROR | ARCHIVED
  execution:
    execution_id: string
    status: PENDING | READY | RUNNING | WAITING | VERIFYING | AWAITING_HUMAN_VERIFICATION | COMPLETED | FAILED | RECOVERING | PAUSED | CANCELLED | BLOCKED
    current_step_id: string|null
    current_worker_run_id: string|null
    attempt: integer
    human_verification:
      required: boolean
      status: PENDING | CONFIRMED | REJECTED
      requested_at: string|null
      completed_at: string|null
      verified_by: string|null
      reason: string|null
  intent:
    original_text: string
    normalized_objective: string
    constraints: object
    inputs: object
    outputs_expected: object
  workflow:
    workflow_id: string|null
    version_id: string|null
    source: KNOWN | NEW | ADAPTIVE
  steps: []
  environment:
    site: object|null
    browser: object|null
    local_files: object|null
    session_refs: []
  verification:
    overall: UNKNOWN | PASS | FAIL | PARTIAL
    assertions: []
  checkpoint:
    latest_id: string|null
    safe_resume_boundary: string|null
  recovery:
    status: NONE | NEEDED | IN_PROGRESS | RESOLVED | ESCALATED
    attempts: integer
    budget_remaining: object
  security:
    policy_status: ALLOWED | APPROVAL_REQUIRED | BLOCKED
    approvals: []
  artifacts: []
  timestamps: {}
```

## 4. Step State

Each step has:

```yaml
step_state:
  step_id: string
  status: PENDING | READY | RUNNING | OBSERVING | VERIFYING | COMPLETED | FAILED | UNCERTAIN | SKIPPED | BLOCKED
  attempts: integer
  latest_worker_run_id: string|null
  precondition_status: PASS | FAIL | UNKNOWN
  verification_status: PASS | FAIL | UNKNOWN
  outputs: object
  evidence: []
```

## 5. State Transition Rules

Allowed examples:

```text
PENDING → READY
READY → RUNNING
RUNNING → OBSERVING
OBSERVING → VERIFYING
VERIFYING → AWAITING_HUMAN_VERIFICATION
AWAITING_HUMAN_VERIFICATION → COMPLETED (on human confirm)
AWAITING_HUMAN_VERIFICATION → RECOVERING (on human reject)
AWAITING_HUMAN_VERIFICATION → CANCELLED
VERIFYING → UNCERTAIN
RUNNING → FAILED
FAILED → RECOVERING
RECOVERING → RUNNING
RECOVERING → AWAITING_HUMAN_VERIFICATION
RECOVERING → PAUSED
RECOVERING → ABORTED
```

Illegal transitions should be rejected by the state engine. Direct transition from `VERIFYING` to `COMPLETED` is prohibited when human verification is configured.

## 6. Logical vs Environmental State

Logical state:
- current workflow step;
- completed steps;
- expected values;
- verification results.

Environmental state:
- current URL;
- page fingerprint;
- authentication reference;
- filesystem artifacts;
- external resource identifiers.

A restart must reconstruct both before resuming.

## 7. Uncertainty

Use `UNKNOWN`/`UNCERTAIN` when WebCMD cannot prove whether an external side effect occurred.

Example:

```text
click Submit
→ browser crashed
→ result = UNCERTAIN
```

Recovery must verify the external state before retrying.

## 8. Last-Known-State

The state engine should retain a compact `last_known_state` snapshot per execution/environment:
- last verified URL;
- last verified page type;
- last successful action;
- last successful workflow step;
- current resource identifiers;
- session reference;
- environment fingerprint.

This snapshot is a restart aid, not a source of unconditional truth.

## 9. Event Projection

The current state should be reconstructible from ordered events:

```text
ExecutionCreated
PlanAccepted
StepStarted
ActionIssued
ObservationCaptured
VerificationEvaluated
CheckpointCreated
StepCompleted
RecoveryStarted
...
```

## 10. Consistency Invariants

1. `current_step_id` must refer to a non-terminal step while execution is active.
2. `COMPLETED` execution requires `verification.overall = PASS` or an explicitly defined partial-success terminal contract.
3. `FAILED` execution must have a failure code.
4. `RECOVERING` requires an active recovery attempt.
5. `APPROVAL_REQUIRED` cannot transition to side-effect execution without approval.
6. Checkpoint references must point to persisted evidence.
7. `COMPLETED` execution requires explicit human confirmation (`human_verification.status = CONFIRMED`). The execution cannot transition directly from `VERIFYING` to `COMPLETED` without this single final gate.

