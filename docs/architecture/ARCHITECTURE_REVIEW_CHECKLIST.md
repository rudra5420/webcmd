# WebCMD — Architecture Review Checklist

Use this before any production coding begins.

## Product
- [ ] WebCMD is defined as an execution runtime, not only a browser agent.
- [ ] Browser automation is isolated behind a worker boundary.
- [ ] Existing Playwright/MCP/browser-use projects are treated as adapters.

## Core Semantics
- [ ] Task, workflow, workflow version, execution and worker run have distinct meanings.
- [ ] State transitions are explicit.
- [ ] Unknown/uncertain side effects are modeled.
- [ ] Verification is separate from execution success.

## Memory/Learning
- [ ] Site memory exists.
- [ ] Last-known-state exists.
- [ ] Interaction and navigation memory exist.
- [ ] Failure/recovery memory exists.
- [ ] Memory has provenance, confidence and freshness.
- [ ] Unverified claims cannot be promoted to trusted workflow knowledge.

## Reliability
- [ ] Checkpoints have safe resume boundaries.
- [ ] External state is revalidated on resume.
- [ ] Recovery has explicit budgets.
- [ ] Non-idempotent actions have uncertainty handling.
- [ ] Handoffs preserve verified context.

## Security
- [ ] Model output cannot grant capabilities.
- [ ] External webpage content is untrusted.
- [ ] Credentials are separate from ordinary memory/state.
- [ ] Approvals are action-specific and expiring.
- [ ] Shell/filesystem/browser capabilities are policy controlled.

## Implementation
- [ ] Mock worker passes the contract.
- [ ] State engine passes transition tests.
- [ ] Checkpoint crash/restart tests pass.
- [ ] Policy bypass tests fail safely.
- [ ] Prompt injection tests fail safely.
- [ ] First end-to-end scenario can be demonstrated.
