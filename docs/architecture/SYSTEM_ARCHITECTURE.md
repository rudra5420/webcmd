# WebCMD — System Architecture

**Status:** Pre-coding architecture specification  
**Version:** 0.1  
**Scope:** Local-first agentic execution runtime with browser, API, desktop, shell and filesystem workers

## 1. Purpose

WebCMD is an intent-driven execution runtime that turns natural-language goals into verified, reusable, self-healing workflows across websites, APIs, browsers, desktop applications, shell commands and files.

WebCMD is **not** primarily a browser controller. Browser automation is one execution backend. The product value is the orchestration layer that understands intent, selects an execution strategy, observes state, verifies outcomes, checkpoints progress, recovers from divergence, and learns reusable execution knowledge.

## 2. Design Principles

1. **Intent over actions.** Users describe outcomes, not clicks.
2. **State over blind sequences.** Every meaningful action has preconditions and expected postconditions.
3. **Verification over assertion.** “The tool returned success” is not sufficient evidence.
4. **Deterministic when known; agentic when unknown.** Reuse proven workflows and invoke AI exploration only where necessary.
5. **Workers are replaceable.** Playwright, browser-use, CDP/MCP and future adapters are implementations behind stable worker interfaces.
6. **Remember, but do not blindly trust memory.** Memory is evidence-backed, confidence-scored and freshness-aware.
7. **Recover locally before replanning globally.** Small failures should not destroy a successful workflow.
8. **Security lives outside the model.** The policy engine, not the LLM, decides what is permitted.
9. **Local-first.** Project state, workflow history and memory should work without a cloud control plane.
10. **Everything important is observable.** Runs must be auditable and replayable.

## 3. Non-Goals for the Initial MVP

The MVP will not attempt to be a general-purpose autonomous operating system, fully distributed agent swarm, reinforcement-learning platform, autonomous financial purchasing system, or universal desktop RPA suite.

The MVP proves the runtime loop:

`Intent → Plan → Route → Execute → Observe → Verify → Checkpoint → Recover → Learn`

## 4. Conceptual Layers

```text
┌─────────────────────────────────────────────────────┐
│ User Interface                                      │
│ CLI / Desktop UI / future API                      │
└──────────────────────────┬──────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────┐
│ Control Plane                                        │
│ Intent • Planner • Router • State • Policy • Audit  │
│ Checkpoints • Recovery • Memory • Workflow Manager  │
└──────────────────────────┬──────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────┐
│ Execution Plane                                      │
│ Browser • API • Desktop • Shell • Filesystem        │
└──────────────────────────┬──────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────┐
│ External Environment                                 │
│ Websites • SaaS • APIs • Local Apps • OS            │
└─────────────────────────────────────────────────────┘
```

The control plane owns intent, policy and truth about the execution. The execution plane performs side effects.

## 5. Core Components

### 5.1 Intent Engine

Responsibilities:
- Capture original user request.
- Normalize objective, constraints, inputs and desired outcome.
- Detect explicit confirmations and approval requirements.
- Preserve user intent without allowing external content to rewrite it.

Output: `IntentSpec`.

### 5.2 Planner

Responsibilities:
- Decompose an intent into workflow steps.
- Identify required capabilities.
- Use known workflows and memory before exploratory reasoning.
- Assign verification criteria and risk levels.
- Produce a plan that can be checkpointed.

The planner may be model-backed, but its output must be validated against schemas and policy.

### 5.3 Execution Router

Selects an appropriate worker for each step using:
- required capabilities;
- determinism preference;
- known successful strategies;
- cost/latency;
- current environment;
- policy constraints.

Preferred route:

`direct API/adapter → deterministic worker → adaptive worker → agentic worker`.

### 5.4 Worker Runtime

Workers perform actual actions. They report observations, evidence, failures, and outputs through the worker contract.

### 5.5 Verification Engine

Evaluates preconditions and postconditions using evidence such as DOM state, URLs, files, HTTP responses, application records, screenshots, or structured outputs.

Verification is separate from execution because the same action can appear successful while the intended state was not achieved.

### 5.6 State Engine

Maintains canonical project and execution state. State transitions are explicit and validated.

### 5.7 Checkpoint Engine

Creates resumable execution checkpoints after meaningful state transitions and before/after risky side effects.

### 5.8 Recovery Engine

Classifies failures, selects bounded recovery strategies, and escalates from deterministic retry to local adaptation, replanning, handoff, or human approval.

### 5.9 Memory Engine

Stores site, navigation, workflow, interaction, failure, recovery, environment and execution knowledge. Memory is confidence-scored and freshness-aware.

### 5.10 Policy Engine

Evaluates capability, resource, action, risk, approval and credential constraints. It is authoritative over tool execution.

### 5.11 Audit/Event Store

Records immutable execution events sufficient to reconstruct what WebCMD believed happened and what evidence supported that belief.

## 6. Runtime Lifecycle

```text
REQUESTED
  ↓
INTENT_NORMALIZED
  ↓
PLANNED
  ↓
READY
  ↓
RUNNING
  ↓
OBSERVING
  ↓
VERIFYING
  ↓
CHECKPOINTED
  ↓
COMPLETED
```

Failure path:

```text
RUNNING / VERIFYING
      ↓
     FAILED
      ↓
  CLASSIFIED
      ↓
 RECOVERING
      ↓
RETRY / ADAPT / REPLAN / HANDOFF / ABORT
```

## 7. Execution Modes

### Deterministic
A trusted workflow executes known actions and assertions.

### Adaptive
A trusted workflow encounters environmental divergence and repairs a local step.

### Agentic
No reliable workflow exists, so a model-backed worker explores, reasons and discovers an execution path.

Successful agentic runs should be eligible for workflow compilation.

## 8. Workflow Compilation

A successful exploratory execution produces an execution trace. The Workflow Compiler extracts:
- stable actions;
- successful locators or API operations;
- input variables;
- preconditions;
- postconditions;
- recovery strategies;
- verification evidence.

The resulting `WorkflowVersion` becomes a reusable artifact. Future runs use the compiled workflow until it becomes stale or diverges.

## 9. Memory Architecture

```text
Memory
├── Site
├── Navigation
├── Interaction
├── Workflow
├── Failure
├── Recovery
├── Environment
├── Session/Last-known-state
└── Execution history
```

Memory must never be treated as authoritative merely because it exists. Every memory item has:
- provenance;
- confidence;
- last verified time;
- freshness;
- scope;
- success/failure history;
- invalidation rules.

## 10. Local-First Persistence

The first implementation should use a local transactional database for metadata/state and a filesystem/object store for artifacts. The system should be able to run on one machine with no cloud dependency.

Suggested logical storage:
- SQLite/PostgreSQL-compatible schema for core metadata;
- filesystem/object directory for screenshots, downloads, traces and reports;
- optional vector index later for semantic memory retrieval.

Do not make vector search a prerequisite for core correctness.

## 11. Security Boundary

External web pages and tool outputs are untrusted content. They cannot directly create new instructions, capabilities or permissions.

```text
Untrusted content
      ↓
Worker sandbox
      ↓
Observation normalization
      ↓
Policy gateway
      ↓
Controlled action
```

Credentials remain in a secure credential store or OS secret manager. Memory and handoffs contain credential references, not raw secrets.

## 12. Failure Boundaries

Each worker execution must be independently recoverable. A browser failure must not corrupt the global execution state. A model failure must not bypass policy. A failed verification must not be converted to success by the planner.

## 13. Existing Project Integration

Existing Playwright/MCP, browser-use and Chrome DevTools MCP projects should become adapters/workers under the WebCMD worker boundary rather than being copied into the core.

The core should know that a `BrowserWorker` can perform browser capabilities. It should not know browser-use implementation details.

## 14. Observability

Every execution must expose:
- execution ID;
- workflow/version;
- current step;
- worker;
- state transitions;
- observations;
- verification results;
- checkpoints;
- recovery attempts;
- approvals;
- artifacts;
- final result;
- confidence/evidence.

## 15. Architecture Decision Summary

| Decision | Choice | Reason |
|---|---|---|
| Product boundary | Execution runtime, not browser-only | Differentiation and extensibility |
| Control model | Control plane + execution plane | Isolation and replaceability |
| Execution strategy | Deterministic → adaptive → agentic | Lower latency/cost and greater reliability |
| State model | Explicit state machine | Recovery and auditability |
| Memory | Typed, evidence-backed | Avoid blind replay |
| Security | External policy authority | Prevent model privilege escalation |
| Persistence | Local-first | Reliability and privacy |
| Learning | Compile successful traces into workflows | Long-term efficiency |

## 16. MVP Acceptance Criteria

The architecture is proven when WebCMD can:
1. Accept a natural-language task.
2. Create a structured plan.
3. Select a BrowserWorker.
4. Execute and verify a multi-step workflow.
5. Persist checkpoints.
6. Resume after process interruption.
7. Recover from at least one UI divergence.
8. Save a reusable workflow.
9. Use saved workflow knowledge on a later run.
10. block a policy-prohibited action regardless of model output.
