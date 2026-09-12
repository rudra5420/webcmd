# WebCMD — Checkpoint Design

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Purpose

A checkpoint is a resumable execution boundary containing enough verified state to determine what has happened, what is safe to repeat, and where execution can continue.

A checkpoint is more than serialized JSON.

## 2. Checkpoint Layers

### Logical Checkpoint
What workflow steps WebCMD considers completed, pending or uncertain.

### Environmental Checkpoint
Relevant external state such as URL, page identity, session reference, resource IDs and environment fingerprint.

### Evidence Checkpoint
Pointers to screenshots, DOM snapshots, API responses, file hashes, assertions and other evidence.

### Recovery Checkpoint
Information describing failed attempts and safe retry/recovery boundaries.

## 3. Creation Rules

Create checkpoints:
- after meaningful successful step verification;
- before high-risk side effects;
- after non-idempotent actions;
- after a recovery succeeds;
- before an intentional handoff;
- immediately before final human verification gate (`PRE_HUMAN_VERIFICATION`);
- before pausing execution.

## 4. Checkpoint Transaction

```text
prepare state
   ↓
flush observations/evidence
   ↓
compute state hash
   ↓
persist checkpoint
   ↓
append CheckpointCreated event
   ↓
mark resume boundary
```

Checkpoint creation must be atomic at the metadata layer.

## 5. State Hash

Each checkpoint should have a deterministic hash over its canonical logical state and references. This detects corruption or accidental mutation.

## 6. Resume Boundary

A checkpoint must identify:
- last verified step;
- next step to attempt;
- any uncertain side effects;
- environment assumptions that must be revalidated;
- policy state;
- required worker capability.

## 7. Safe Resume Algorithm

```text
load latest checkpoint
      ↓
validate integrity
      ↓
restore logical state
      ↓
re-observe environment
      ↓
compare against checkpoint expectations
      ↓
if compatible → resume
if changed → recovery/adaptation
if uncertain → verify external side effect first
```

Never resume solely because a checkpoint file exists.

## 8. Before/After Side-Effect Pattern

For non-idempotent operations:

```text
Checkpoint A
   ↓
precondition verification
   ↓
issue side effect
   ↓
observation
   ↓
postcondition verification
   ↓
Checkpoint B
```

If the process dies between the side effect and verification, resume in `UNCERTAIN` mode and determine actual external state before retrying.

## 9. Retention

Retain enough checkpoints to support:
- latest resume;
- recovery comparison;
- audit trail;
- workflow learning.

Older checkpoints may be compacted if immutable event history and required evidence remain available.

Checkpoints created with `PRE_HUMAN_VERIFICATION` trigger are explicitly protected from automated pruning, ensuring that long-pending human approvals or process restarts during the verification gate can always resume safely without task re-execution.

## 10. Corruption Handling

If a checkpoint fails integrity validation:
- do not resume from it;
- use the previous valid checkpoint;
- mark the damaged checkpoint;
- record an audit event;
- trigger recovery if necessary.

## 11. Checkpoint Security

Never embed raw credentials. References are permitted. Artifacts containing sensitive data must obey artifact security and retention rules.

## 12. Acceptance Tests

1. Kill process after a verified step; restart and continue.
2. Kill process immediately after a non-idempotent action; restart and detect uncertainty.
3. Modify browser state before resume; trigger revalidation.
4. Corrupt checkpoint; fall back safely.
5. Resume with expired policy approval; block until re-approved.
6. Kill process while awaiting final human verification; restart and resume in `AWAITING_HUMAN_VERIFICATION` state without re-executing task.
