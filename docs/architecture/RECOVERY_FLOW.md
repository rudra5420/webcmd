# WebCMD — Recovery Flow

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Purpose

Recovery restores forward progress after an execution failure, environmental change, verification failure, timeout, worker crash or uncertain external side effect.

## 2. Recovery Hierarchy

```text
Failure
  ↓
classify
  ↓
verify whether side effect happened
  ↓
retry deterministically?
  ↓ no
local repair?
  ↓ no
adaptive replan?
  ↓ no
handoff?
  ↓ no
human / abort
```

## 3. Failure Classes

- `TRANSIENT`
- `TIMEOUT`
- `NETWORK`
- `ELEMENT_NOT_FOUND`
- `STATE_MISMATCH`
- `AUTHENTICATION`
- `PERMISSION`
- `POLICY_BLOCK`
- `DATA_ERROR`
- `ENVIRONMENT_CHANGE`
- `WORKER_CRASH`
- `VERIFICATION_FAILED`
- `SIDE_EFFECT_UNCERTAIN`
- `UNKNOWN`

## 4. Recovery Strategies

### Retry
Use for bounded transient/idempotent failures.

### Re-observe
Reload or inspect the current environment before retrying.

### Locator Adaptation
Try known alternative interaction strategies.

### Local Replan
Change only the failed step while preserving the surrounding workflow.

### Global Replan
Use when assumptions or workflow structure have materially changed.

### Handoff
Move execution to another capable worker.

### Human Escalation
Required when policy, risk, uncertainty or recovery budget requires it.

### Abort
Terminate safely when continuation is unsafe or impossible.

## 5. Recovery Budget

Every execution receives budgets:
- maximum attempts per step;
- maximum recovery depth;
- maximum total execution time;
- maximum model/tool budget;
- maximum side-effect retries.

Budgets are policy-controlled.

## 6. Recovery State Machine

```text
FAILED
  ↓
CLASSIFYING
  ↓
VERIFYING_EXTERNAL_STATE
  ↓
RECOVERING
  ├── RETRYING
  ├── ADAPTING
  ├── REPLANNING
  ├── HANDOFF_PENDING
  ├── APPROVAL_PENDING
  └── ABORTING
```

## 7. Side-Effect Uncertainty

Example: order submission returns a network error.

Do **not** retry immediately.

```text
network failure
 ↓
query external order state
 ↓
found order → mark action applied
not found → retry if permitted
still unknown → human escalation
```

This prevents duplicate side effects.

## 8. Learning from Recovery

Successful recovery strategies should be recorded as `RecoveryMemory` with:
- triggering failure;
- environment/site;
- prior strategy;
- successful repair;
- evidence;
- confidence;
- freshness.

Repeated successful repairs may be promoted into workflow rules.

## 9. Recovery vs Replanning

Use local recovery when the workflow objective and environment remain mostly valid. Use global replanning when the target resource, business process or prerequisites have changed.

## 10. Recovery Safety

A model cannot bypass a policy block by reframing the same action. Recovery must re-enter policy evaluation for every new side effect.

## 11. Human Rejection Recovery & Review Escalation

When human verification at the single final gate rejects the execution result:
1. The execution transitions from `AWAITING_HUMAN_VERIFICATION` to `RECOVERING` with failure code `HUMAN_REJECTED: <reason>`.
2. The pre-verification checkpoint is preserved; earlier verified steps are not blindly repeated.
3. The rejection reason is routed to `RecoveryEngine.handle_human_rejection()`, initiating a bounded review or global replan.
4. If recovery replanning succeeds and re-executes, the new result must pass automated verification and re-enter the final human verification gate.
5. Human rejection is recorded as a negative signal in failure memory, preventing the rejected path from being reinforced as a trusted workflow.

## 12. Acceptance Tests

1. Transient failure retries within budget.
2. Changed button triggers local adaptation.
3. Unknown side effect is verified before retry.
4. Recovery budget exhaustion leads to escalation.
5. A policy block remains a hard boundary.
6. Successful repair is stored as learning evidence.
7. Human rejection of final verification triggers recovery review/replan escalation while preserving pre-verification checkpoint.

