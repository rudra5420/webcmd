# WebCMD — Security Model

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Security Objective

WebCMD must safely execute user-authorized work in environments containing arbitrary, potentially malicious external content.

Primary threats include:
- prompt injection from websites;
- credential leakage;
- unintended side effects;
- privilege escalation by model output;
- malicious tool outputs;
- workflow corruption;
- replay of stale approvals;
- unsafe automation after environment change;
- sensitive artifact exposure.

## 2. Trust Domains

```text
T0 — User/system policy
T1 — WebCMD control plane
T2 — Worker runtime
T3 — Model-generated plans
T4 — External tool outputs
T5 — Website/page content
```

T5 content is untrusted. Model output is not a permission boundary.

## 3. Capability-Based Security

Actions require explicit capabilities:

```text
capability
   + resource
   + action
   + risk
   + policy
   → permit / deny / approval
```

Example:

```text
browser.write + example.com + submit + HIGH
→ approval required
```

## 4. Policy Engine

The policy engine is authoritative.

Rules may define:
- allowed domains;
- blocked domains;
- read/write permissions;
- shell capabilities;
- filesystem boundaries;
- financial/message/purchase approvals;
- resource-specific restrictions;
- time windows;
- execution budgets.

The LLM may propose, but cannot modify policy.

## 5. Prompt Injection Defense

Separate instructions from content:

```text
USER INTENT
SYSTEM/POLICY
WORKFLOW
MODEL PLAN
TOOL OUTPUT
WEB CONTENT
```

Web content is data. It cannot be promoted into workflow instructions unless the planner explicitly treats it as user-authorized input and passes policy validation.

Examples of suspicious page instructions must be treated as untrusted data.

## 6. Credential Security

Credentials live in a secure store/OS secret manager. WebCMD uses references such as:

`credential_ref: github_primary`

Never persist raw:
- passwords;
- session cookies;
- access tokens;
- refresh tokens;
- OTPs;
- payment card secrets.

## 7. Session Isolation

Browser sessions should be scoped per project/profile where practical. Sensitive sessions must not be accidentally reused by unrelated projects.

## 8. Side-Effect Risk Classification

Suggested levels:

`LOW` — read-only navigation/search.  
`MEDIUM` — file creation, non-public edits.  
`HIGH` — sending messages, deleting data, changing settings, transactions.  
`CRITICAL` — actions with severe irreversible consequences.

High/critical actions normally require explicit policy and/or approval.

## 9. Approval Semantics

Approval must bind:
- execution ID;
- step/action hash;
- target resource;
- scope;
- expiry;
- user identity.

An approval cannot authorize a different action because the model changed its plan.

## 10. Human Verification Gate Authority

The single final human verification gate exists strictly outside LLM authority (Trust Domain T0).
- The LLM, prompt outputs, and worker agents cannot forge or assert `human_verified=True`.
- The transition from `AWAITING_HUMAN_VERIFICATION` to `COMPLETED` requires explicit confirmation via the operator CLI (`webcmd approve` / interactive prompt) or an explicit `--auto-approve` flag passed at runtime invocation.
- Automated verification passing is a prerequisite to reach the gate, never a bypass of the gate.
- All decisions are immutably recorded in the append-only audit log with execution ID, operator identity, decision, reason, and automated verification status.

## 11. Sandboxing

Workers should operate with least privilege:
- restricted filesystem roots;
- restricted shell commands;
- browser domain allowlists where practical;
- isolated subprocesses;
- bounded network access.

## 12. Auditability

Record:
- who/what initiated execution;
- plan hash/version;
- policy decision;
- worker actions;
- observations/evidence references;
- approvals;
- human verification decisions;
- recovery attempts;
- final result.

Audit records should be append-only.

## 13. Memory Security

Memory must have scope and access controls. Site memories from one project or identity should not automatically leak into another.

Sensitive information should be redacted before memory promotion.

## 14. Artifact Security

Artifacts may contain sensitive personal or business information. Store with access controls, hashes and retention policies.

## 15. Safe Model Interaction

Models receive the minimum required context. Secrets and high-risk policy internals should not be unnecessarily exposed to the model.

## 16. Security Acceptance Tests

1. Website prompt injection cannot grant a capability.
2. Model cannot bypass a blocked domain.
3. Shell worker cannot exceed its configured root/command policy.
4. Raw credentials do not appear in normal logs/memory/handoffs.
5. Expired approval is rejected.
6. Changed action invalidates prior approval.
7. Sensitive memory is scoped correctly.
8. Model outputs or worker payloads cannot forge human confirmation or bypass the final verification gate.

