# WebCMD — Memory and Learning Architecture

**Status:** Pre-coding architecture specification  
**Version:** 0.1

## 1. Purpose

WebCMD should improve with experience without requiring blind model retraining. It learns from verified execution evidence and uses that knowledge to reduce exploration, improve reliability and adapt to website/environment changes.

The core rule is:

> **Remember evidence, not guesses.**

## 2. Memory Types

```text
Site Memory
Navigation Memory
Interaction Memory
Workflow Memory
Failure Memory
Recovery Memory
Environment Memory
Session / Last-Known-State Memory
Execution History
User Preference Memory (scoped and optional)
```

## 3. Site Memory

Stores stable site-level knowledge:
- domain;
- common entrypoints;
- page types;
- authentication method/reference;
- known interaction patterns;
- last visit;
- last verified visit;
- environment fingerprints.

Example:

```yaml
site:
  domain: example.com
  last_visit: 2026-09-12T10:42:31
  last_verified_page: reports_dashboard
  known_entrypoints:
    - /dashboard
    - /reports
  authentication: session_ref:site_session_01
```

## 4. Last-Known-State Memory

On each successful visit, record:
- last verified URL;
- page semantic type;
- active workflow;
- current resource identifiers;
- session reference;
- last successful step;
- last verified timestamp.

This allows a future command such as “continue where I left off” to resolve from evidence-backed session context.

## 5. Navigation Memory

Store successful transitions:

`dashboard → reports → monthly → download`.

Each transition includes:
- strategy;
- evidence;
- success count;
- failure count;
- last verified time.

## 6. Interaction Memory

Store how an element or resource was successfully targeted:

```yaml
target: Download
strategies:
  - type: aria
    success_count: 12
    failure_count: 1
  - type: css
    success_count: 2
    failure_count: 7
  - type: visual
    success_count: 1
```

Future execution ranks strategies rather than asking the model to rediscover them.

## 7. Workflow Memory

Represents proven reusable procedures, normally linked to immutable WorkflowVersions.

A workflow may store:
- success rate;
- median execution time;
- average recovery count;
- last successful execution;
- known failure modes.

## 8. Failure Memory

For repeated failures:

```text
site
+ page type
+ action
+ failure
+ successful repair
```

This can produce a site-specific fallback rule.

## 9. Recovery Memory

Recovery memory stores successful adaptation strategies. It should only be promoted after successful verification.

## 10. Confidence Model

Each memory item has a confidence score from 0 to 1, but confidence is not truth. It is a ranking signal.

A conceptual score may combine:

`base_success_rate × recency × environment_similarity × evidence_quality`.

Keep the exact formula configurable.

## 11. Freshness and Decay

Memory becomes stale as the environment changes.

Use:
- last verified timestamp;
- site change indicators;
- failure history;
- environment fingerprint divergence.

Example policy:
- high-confidence + recently verified → use directly with normal verification;
- medium-confidence → use as hint and verify aggressively;
- low-confidence/stale → exploratory validation first.

## 12. Memory Retrieval

Retrieval should be hierarchical:

```text
exact site/workflow match
      ↓
exact page/action match
      ↓
related workflow/site pattern
      ↓
semantic retrieval
      ↓
new exploration
```

Do not require vector search for exact deterministic matches.

## 13. Learning Pipeline

```text
execution
  ↓
observations
  ↓
automated verification
  ↓
final human verification gate
  ↓
experience extraction (distinguished by gate decision)
  ↓
candidate memories
  ↓
quality filters
  ↓
store + confidence (0.95 confirmed vs 0.70 automated vs negative on reject)
  ↓
promotion to workflow/rule when proven
```

### Human Verification Gate Signal Distinction

The single final human verification gate provides an authoritative training and confidence feedback loop:

1. **Human Confirmation (`CONFIRMED`)**:
   - Stores experiential memories with high initial confidence (0.95).
   - Provenance explicitly tags `verification_type: human_confirmed` and `human_verified: true`.
   - Workflows qualify for promotion and direct reuse.

2. **Automated Verification Only (`automated_only`)**:
   - Stores experiential memories with baseline confidence (0.70).
   - Provenance tags `verification_type: automated_only` and `human_verified: false`.
   - Requires additional verified runs or human confirmation before unconditional trust.

3. **Human Rejection (`REJECTED`)**:
   - Stores failure memory (`MemoryType.FAILURE`) with low confidence (0.20) and operator rejection rationale.
   - Does **not** strengthen or promote the candidate workflow.
   - Signals the planner and retriever to avoid or modify the rejected path on subsequent executions.


## 14. What Counts as Learning

Good learning:
- a stable locator repeatedly succeeds;
- a route consistently works;
- a known UI change has a verified repair;
- an API endpoint is proven reliable;
- a recovery strategy repeatedly resolves a failure.

Bad learning:
- one hallucinated model assertion;
- unverified page instructions;
- assumptions copied from arbitrary websites;
- raw secrets;
- actions that succeeded without proof.

## 15. Memory Promotion

A candidate strategy can be promoted when it meets configurable thresholds, for example:
- at least N successful verified uses;
- no unresolved contradictory evidence;
- adequate confidence;
- compatible security policy.

Promotion creates a new immutable workflow/rule version.

## 16. Memory Invalidation

Invalidate or downgrade memory when:
- repeated failures occur;
- site fingerprint changes materially;
- user explicitly corrects WebCMD;
- security policy changes;
- source artifact expires.

Invalidation is preferable to destructive deletion when auditability matters.

## 17. Human Correction

Users should be able to say:
- “That is the wrong page.”
- “Always use this account for this site.”
- “Never submit automatically.”

Corrections should become scoped memory/policy, not hidden model instructions.

## 18. Privacy Boundaries

Memory is project-scoped by default. Cross-project learning requires explicit configuration.

## 19. Long-Term Learning Evolution

The system can later support skill mining, pattern clustering and model fine-tuning, but the initial learning system should rely on structured evidence and workflow compilation rather than online self-training.

## 20. Signature Behavior

A mature site experience should evolve:

`Unknown → Explored → Learned → Familiar → Optimized → Adaptable`.

The objective is not to eliminate AI; it is to use AI where novelty exists and reuse proven knowledge everywhere else.
