# WebCMD — Handoff Protocol

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Purpose

A handoff transfers execution responsibility from one worker/agent to another without losing the verified context required for safe continuation.

Examples:
- BrowserWorker → APIWorker
- APIWorker → BrowserWorker
- BrowserWorker → DesktopWorker
- Worker → human approval
- Agentic worker → deterministic compiled workflow

## 2. Handoff Principles

1. Transfer only necessary context.
2. Preserve evidence references.
3. Never transfer raw credentials in ordinary payloads.
4. Preserve the exact execution objective and constraints.
5. Make the handoff resumable and auditable.
6. The target worker must independently validate its preconditions.

## 3. Handoff Envelope

```yaml
handoff:
  handoff_id: string
  execution_id: string
  source_worker_run_id: string
  target_worker_type: string
  reason: RECOVERY | CAPABILITY_CHANGE | OPTIMIZATION | POLICY | HUMAN_APPROVAL
  objective: string
  step_context:
    current_step_id: string
    completed_steps: []
    pending_steps: []
  logical_state: object
  environmental_state_reference: string
  observations: []
  verification_results: []
  artifacts: []
  memory_hints: []
  credential_references: []
  permissions: []
  constraints: object
  checkpoint_reference: string
  expires_at: timestamp
```

## 4. Handoff Lifecycle

```text
REQUESTED
  ↓
VALIDATED
  ↓
PACKAGED
  ↓
TRANSFERRED
  ↓
ACCEPTED
  ↓
TARGET_REVALIDATES
  ↓
EXECUTING
```

If rejected:

`REJECTED → RECOVERY / ALTERNATE WORKER / HUMAN`

## 5. Revalidation

The target worker must verify:
- required capability still exists;
- policy permits the action;
- relevant external state is compatible;
- checkpoint is valid;
- assumptions have not expired.

## 6. Browser-to-API Example

If the browser discovers a stable API endpoint:

```text
BrowserWorker discovers endpoint
        ↓
records evidence
        ↓
Handoff to APIWorker
        ↓
APIWorker validates endpoint/auth reference
        ↓
API call
        ↓
verify output
        ↓
checkpoint
```

## 7. Human Approval Handoff

A human approval is a special target. It must include:
- exact action proposed;
- resource;
- risk;
- evidence gathered;
- consequences;
- expiry.

Approval must be specific enough that it cannot be repurposed for an unrelated action.

## 8. Idempotency

The handoff protocol must indicate whether the current step is safe to retry. Non-idempotent actions require verification before a new worker executes them.

## 9. Security

Handoff payloads are signed/hashed where practical and stored as audit artifacts. Secret values are replaced with secure references.

## 10. Acceptance Tests

- Browser → API preserves task objective and evidence.
- Target rejects unsupported capability.
- Target rejects expired checkpoint.
- Human approval cannot be reused for another action.
- Credential references remain references.
