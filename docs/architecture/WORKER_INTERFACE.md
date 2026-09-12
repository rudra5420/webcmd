# WebCMD — Worker Interface

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Purpose

Workers are replaceable adapters that execute actions in an external environment. The core runtime must depend only on the worker contract, never on a worker's internal library.

Initial worker families:
- BrowserWorker
- APIWorker
- ShellWorker
- FilesystemWorker
- DesktopWorker (later)

Existing Playwright/MCP, browser-use and Chrome DevTools MCP implementations should fit behind this boundary.

## 2. Worker Responsibilities

A worker must:
- declare capabilities;
- validate whether it can execute a step;
- prepare its environment;
- perform the action;
- emit normalized observations;
- return artifacts and outputs;
- report failures using stable codes;
- support cancellation where feasible;
- preserve enough information for verification and recovery.

A worker must **not**:
- change global policy;
- invent user permissions;
- silently mutate workflow definitions;
- claim successful completion without returning evidence;
- store raw credentials in ordinary output.

## 3. Conceptual Contract

```text
initialize(context) -> WorkerReady
capabilities() -> CapabilitySet
prepare(step, context) -> PreparedAction
execute(prepared_action) -> WorkerResult
observe(context) -> ObservationSet
verify(context, verification_spec) -> VerificationResult
pause() -> PauseResult
resume(context) -> ResumeResult
cancel(reason) -> CancelResult
shutdown() -> ShutdownResult
```

Not every backend needs native support for every lifecycle operation. Unsupported operations must be explicit rather than silently emulated.

## 4. Capability Model

Example capabilities:

```yaml
browser.navigate
browser.click
browser.type
browser.select
browser.download
browser.screenshot
browser.dom_read
browser.evaluate_js
api.http_get
api.http_post
shell.execute
filesystem.read
filesystem.write
filesystem.rename
```

Capabilities should be versioned and policy-addressable.

## 5. Worker Context

The runtime supplies a context containing:
- `execution_id`
- `task_id`
- `step_id`
- `checkpoint_reference`
- `allowed_capabilities`
- `policy_decision`
- `input_bindings`
- `environment_reference`
- `time_budget`
- `attempt_number`
- `memory_hints`

The context must not contain unnecessary secrets.

## 6. Prepared Action

A prepared action is a validated, execution-ready representation:

```yaml
prepared_action:
  action_id: ...
  worker_type: browser
  capability: browser.click
  target:
    semantic_name: "Download"
    locator_strategy: aria
  preconditions: [...]
  expected_postconditions: [...]
  risk_level: medium
```

## 7. Worker Result

```yaml
result:
  status: succeeded | failed | cancelled | blocked | uncertain
  outputs: {...}
  observations: [...]
  artifacts: [...]
  evidence: [...]
  failure_code: null
  retryable: false
  side_effect_status: none | partial | applied | unknown
```

`uncertain` is critical. An action may have happened while confirmation is unavailable.

## 8. BrowserWorker Requirements

BrowserWorker should support:
- session attach/create;
- navigation;
- semantic/DOM interaction;
- screenshots;
- downloads;
- page observation;
- structured evidence collection;
- optional browser-use/LLM fallback;
- CDP/Playwright/MCP adapters.

The browser worker should implement a strategy hierarchy:

`known locator → semantic locator → DOM pattern → visual/AI fallback`.

## 9. APIWorker Requirements

APIWorker should support:
- HTTP request execution;
- authentication references;
- response normalization;
- status/schema validation;
- rate/time budgets;
- idempotency keys where relevant.

Prefer API execution to browser execution when a permitted, reliable API exists.

## 10. Cancellation

Cancellation must be cooperative and explicit. A worker that cannot safely cancel a side effect must return `uncertain` and trigger recovery/verification rather than pretending cancellation succeeded.

## 11. Idempotency

Workers should declare whether an action is:
- idempotent;
- conditionally idempotent;
- non-idempotent;
- unknown.

Non-idempotent actions require stricter recovery rules.

## 12. Worker Registration

Workers register:
- identity/version;
- capability list;
- environment requirements;
- trust level;
- supported cancellation semantics;
- supported observation types.

## 13. Versioning

The worker interface itself is versioned. Worker implementations must advertise compatibility.

## 14. Security Boundary

The worker receives permissions from the runtime; it does not grant them to itself. Any request for elevated capability must return `BLOCKED_BY_POLICY` and enter approval handling.

## 15. Testing Contract

Every worker must pass:
- capability declaration tests;
- normal success tests;
- malformed input tests;
- timeout/cancellation tests;
- evidence emission tests;
- policy rejection tests;
- uncertain-result tests;
- recovery integration tests.
