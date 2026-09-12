# WebCMD — Implementation Plan

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Implementation Rule

No production implementation should begin until the architecture pack passes cross-document consistency review.

Required documents:
1. SYSTEM_ARCHITECTURE.md
2. DATA_MODEL.md
3. WORKER_INTERFACE.md
4. PROJECT_STATE_SCHEMA.md
5. CHECKPOINT_DESIGN.md
6. HANDOFF_PROTOCOL.md
7. RECOVERY_FLOW.md
8. SECURITY_MODEL.md
9. MEMORY_AND_LEARNING.md
10. IMPLEMENTATION_PLAN.md

## 2. Phase 0 — Architecture Freeze

Deliver:
- glossary and invariants;
- state machine;
- worker contract;
- data model;
- checkpoint semantics;
- handoff semantics;
- recovery matrix;
- security model;
- memory/learning model;
- test scenarios.

Gate: no unresolved contradiction about task/execution/workflow/state/worker semantics.

## 3. Phase 1 — WebCMD Kernel

Implement:
- project registry;
- task/execution creation;
- state machine;
- event store;
- structured logging;
- local persistence;
- CLI skeleton.

Acceptance:
`webcmd create`, `webcmd status`, `webcmd inspect`, `webcmd cancel` work without browser intelligence.

## 4. Phase 2 — Worker Runtime

Implement worker registry and adapter boundary.

First integration:
- Playwright adapter;
- Chrome DevTools/CDP adapter where practical;
- existing MCP/browser-use integration behind BrowserWorker.

Acceptance:
A worker can execute a step and return normalized evidence/results.

## 5. Phase 3 — Planner and Execution Router

Implement:
- IntentSpec generation;
- structured plan schema;
- capability matching;
- deterministic-first routing;
- policy pre-check.

Acceptance:
The same user intent can be routed to different workers based on capability rather than hardcoded browser logic.

## 6. Phase 4 — Verification Engine

Implement assertion types:
- URL/state assertions;
- DOM/semantic assertions;
- API response/schema assertions;
- file existence/hash assertions;
- record presence assertions.

Acceptance:
A worker cannot mark an execution successful without passing required verification.

## 7. Phase 5 — Checkpoint/Resume

Implement:
- checkpoint creation;
- integrity/hash validation;
- latest valid checkpoint lookup;
- environment revalidation;
- resume.

Acceptance:
Kill/restart tests resume safely.

## 8. Phase 6 — Recovery

Implement:
- failure classification;
- retry policies;
- uncertain side-effect handling;
- local repair;
- bounded replanning;
- escalation.

Acceptance:
At least three failure scenarios recover without restarting from zero.

## 9. Phase 7 — Handoff

Implement worker-to-worker handoff envelopes and revalidation.

Acceptance:
Browser → API → Browser scenario works with preserved execution context.

## 10. Phase 8 — Memory and Learning

Implement first without vector databases:
- site profiles;
- last-known-state;
- navigation memory;
- interaction strategy memory;
- workflow statistics;
- failure/recovery memory;
- confidence/freshness;
- exact retrieval.

Then implement workflow compilation from successful execution traces.

Acceptance:
A task executed once creates reusable knowledge and a later run uses that knowledge with less exploration.

## 11. Phase 9 — Policy and Approvals

Implement:
- capability permissions;
- domain/resource restrictions;
- risk levels;
- approval requests;
- approval expiry;
- shadow mode;
- audit records.

Acceptance:
Model cannot perform policy-blocked actions.

## 12. Phase 10 — CLI UX

Initial commands:

```bash
webcmd do "..."
webcmd run <workflow> [inputs]
webcmd teach <name>
webcmd skills
webcmd runs
webcmd inspect <execution-id>
webcmd resume <execution-id>
webcmd approve <execution-id>
webcmd repair <workflow>
webcmd cancel <execution-id>
webcmd policy list
```

## 13. Phase 11 — UI

Build after the runtime is stable.

Views:
- active runs;
- execution trace;
- workflow library;
- site memory;
- checkpoints;
- approvals;
- policies;
- artifacts;
- audit history.

## 14. Phase 12 — Hardening

Add:
- crash recovery;
- concurrency limits;
- worker isolation;
- structured telemetry;
- secret handling review;
- prompt injection test suite;
- regression suite for website changes;
- backup/restore.

## 15. Test Strategy

### Unit tests
Schemas, state transitions, policy rules, memory scoring, checkpoint integrity.

### Integration tests
Worker contract, browser adapter, API adapter, persistence.

### Scenario tests
Normal completion, worker crash, network failure, UI change, authentication expiration, uncertain side effect, policy block, prompt injection, resume.

### Adversarial tests
Website content attempts to override instructions, inject commands, request secrets or redirect execution.

## 16. Cross-Document Consistency Matrix

| Concept | Architecture | Data | Worker | State | Checkpoint | Handoff | Recovery | Security | Memory | Implementation |
|---|---|---|---|---|---|---|---|---|---|---|
| Intent | ✓ | ✓ |  | ✓ |  | ✓ | ✓ | ✓ |  | ✓ |
| Task | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Workflow | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Worker | ✓ | ✓ | ✓ | ✓ |  | ✓ | ✓ | ✓ |  | ✓ |
| Verification | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Checkpoint | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Recovery | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Policy | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Memory | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## 17. MVP Demo Definition

The recommended first end-to-end demo:

```text
User:
"Go to this portal, download my latest report,
rename it, verify it exists, and summarize it."

Intent
  ↓
Memory Retrieval
  ↓
Planner
  ↓
Policy Check
  ↓
Execution Router
  ↓
BrowserWorker (download)
  ↓
FilesystemWorker (rename)
  ↓
Observe
  ↓
Automated Verification
  ↓
Recovery if necessary
  ↓
Pre-Verification Checkpoint
  ↓
FINAL HUMAN VERIFICATION
  ↓
Complete
  ↓
Learn / Update Memory
```

Then deliberately terminate the runtime and restart it. WebCMD must resume from the latest verified checkpoint (`PRE_HUMAN_VERIFICATION`) without re-executing completed work.

Finally, repeat the task. WebCMD should reuse the learned workflow/site memory rather than rediscovering everything.

## 18. Phase Gates

Do not advance when:
- state transitions are ambiguous;
- checkpoint resume is unreliable;
- worker contract leaks implementation details;
- policy can be bypassed by model output;
- successful runs are not verifiably distinguishable from failures;
- memory can promote unverified claims.

## 19. First Coding Ticket Set

1. Create repository/docs structure.
2. Implement schema validation types.
3. Implement event model.
4. Implement execution state machine.
5. Implement local persistence.
6. Implement Worker interface and mock worker.
7. Implement policy gateway.
8. Implement checkpoint service.
9. Implement verification service.
10. Implement recovery state machine.
11. Integrate BrowserWorker.
12. Build first end-to-end scenario.

## 20. Post-MVP Roadmap

Potential later capabilities:
- distributed workers;
- parallel task DAGs;
- richer desktop automation;
- skill marketplace/import/export;
- stronger environment fingerprinting;
- vector/graph memory;
- learned workflow optimization;
- team/shared policies;
- remote worker execution;
- advanced observability.

These must not weaken the local-first core or policy model.

## 21. Phase 15 — Single Final Human Verification Gate

**Objective:** Add a single final human verification step at the end of execution without modifying prior autonomous execution or adding approval steps before individual actions.

**Completed Implementations:**
1. **State Machine (`src/webcmd/state/enums.py`, `machine.py`)**:
   - Added `ExecutionStatus.AWAITING_HUMAN_VERIFICATION`.
   - Added `HumanVerificationDecision` (`PENDING`, `CONFIRMED`, `REJECTED`).
   - Allowed transitions: `VERIFYING -> AWAITING_HUMAN_VERIFICATION`, `AWAITING_HUMAN_VERIFICATION -> COMPLETED | RECOVERING | CANCELLED`.
2. **Persistence & Data Model (`src/webcmd/storage/`)**:
   - `HumanVerificationMetadata` with `required`, `status`, `requested_at`, `completed_at`, `verified_by`, `reason`.
   - Updated SQLite schema with `human_verification` column and automatic JSON serialization/deserialization.
   - Added domain events `HumanVerificationRequested` and `HumanVerificationDecided`.
3. **Pre-Verification Checkpoint (`src/webcmd/checkpoint/manager.py`)**:
   - Added `CheckpointTrigger.PRE_HUMAN_VERIFICATION`, triggered immediately before gate.
   - Protected from eviction/pruning; allows restarts during approval wait without losing progress.
4. **Security & Auditability (`src/webcmd/security/audit.py`)**:
   - Gate operates strictly outside LLM authority (Trust Domain T0).
   - Append-only audit logger records all confirmation/rejection decisions with actor, decision, timestamp, reason, and automated verification status.
5. **Recovery Escalation (`src/webcmd/recovery/engine.py`)**:
   - Added `handle_human_rejection` to budget and escalate rejections into bounded reviews/replanning.
6. **Experiential Memory Distinction (`src/webcmd/memory/engine.py`)**:
   - Human-confirmed execution sets initial confidence to 0.95 and tags `human_verified=True`.
   - Automated-only execution sets initial confidence to 0.70.
   - Human rejection stores negative failure signal (`human_rejected=True`, confidence 0.20) without strengthening workflow.
7. **CLI Integration (`src/webcmd/cli/app.py`)**:
   - Interactive summary display with `[1] Confirm execution / [2] Reject execution`.
   - Non-interactive and scriptable `webcmd approve <id>` / `webcmd confirm <id>`.
   - `webcmd reject <id> [--reason <reason>]`.
   - `--auto-approve` / `--auto-confirm` option in `webcmd do` for headless CI/automated testing.

