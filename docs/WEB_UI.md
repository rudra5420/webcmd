# WebCMD — Local Web Interface & Control Center

WebCMD provides a local web-based control and visualization dashboard designed for live demonstration, workflow inspection, and operator control.

The web interface visualizes the complete WebCMD lifecycle without moving the core execution runtime into browser JavaScript. The underlying runtime (`Orchestrator`, `DatabaseManager`, `CheckpointManager`, `MemoryEngine`, `RecoveryEngine`, `PolicyEngine`) remains the authoritative single source of truth.

---

## 1. Quick Start

### Launch with WebCMD CLI:
```bash
webcmd web
```

### Launch on Custom Port / Host:
```bash
webcmd web --port 8080 --host 0.0.0.0
```

### Launch with Python Module:
```bash
python -m webcmd.web 8000
```

### Access in Browser:
```text
http://127.0.0.1:8000
```

---

## 2. Architecture

```text
       Web Browser (Chrome / Edge / Firefox)
                    │
                    ▼
         WebCMD Web Dashboard (SPA)
        (HTML5 / CSS3 / Vanilla JS)
                    │
         REST API   │   WebSocket Stream
                    ▼
        FastAPI / Uvicorn Server
      (src/webcmd/web/server.py)
                    │
                    ▼
          WebCMD Core Runtime
    (src/webcmd/core/orchestrator.py)
 ┌──────────────────┬──────────────────┐
 │ Intent Engine    │ Verification     │
 │ Planner & Router │ Checkpoints      │
 │ Memory Engine    │ Recovery Engine  │
 │ Policy & Vault   │ Audit Logger     │
 └──────────────────┴──────────────────┘
                    │
                    ▼
              Worker Runtime
 (Playwright • BrowserUse • HTTP • FS • Shell)
```

---

## 3. Dashboard Component Tour

### 1. Header & Landing Mission Banner
- Brand title with version indicator (`v0.1.0`).
- Real-time connection status indicator with dynamic WebSocket health dot (`connected` / `disconnected`).
- One-sentence mission statement:
  > *"WebCMD turns natural-language intent into verified, reusable, self-healing digital workflows with strict human verification gating and memory."*

### 2. Task Input & Action Controls
- Multiline natural language task input with example chips ("Download monthly report", "Verify login portal", "Extract customer records").
- **Auto-Confirm Gate** toggle: For unattended automation, regression tests, and headless CI runs.
- Execution controls: `Run Task`, `Cancel`, `Sync`.

### 3. Canonical Execution Timeline (12-Stage Stepper)
Visual representation of the canonical WebCMD lifecycle with live state badges (`pending`, `active`, `completed`, `waiting-gate`, `recovering`):
```text
[1. Intent] ──► [2. Memory] ──► [3. Plan] ──► [4. Policy] ──► [5. Execute] ──► [6. Observe]
     │
     ▼
[7. Verify] ──► [8. Checkpoint] ──► [9. Recover] ──► [10. Human Gate] ──► [11. Complete] ──► [12. Learn]
```

### 4. Single Final Human Verification Gate
Triggered only after execution finishes and automated verification passes:
- **Task Objective Summary**: Original user request.
- **Automated Verification Checks**:
  - `✓ Intent objective verified`
  - `✓ Preconditions and postconditions satisfied`
  - `✓ Execution integrity validated`
  - `✓ Checkpoint saved: PRE_HUMAN_VERIFICATION`
- **Execution Result Box**: Code-formatted JSON or output text.
- **Action Buttons**:
  - `[ CONFIRM RESULT ]`: Transitions to `COMPLETED`, logs audit entry, and stores experiential memory with **confidence 0.95**.
  - `[ REJECT RESULT ]`: Opens rejection feedback modal. Submitting feedback transitions to `RECOVERING` with failure code `HUMAN_REJECTED: <reason>` and logs a negative training signal.

### 5. Site & Experiential Memory Panel
Visualizes persistent memory for the active domain:
- **Domain**: Target website/host.
- **Last Visit**: Relative timestamp.
- **Known Workflow**: Proven cached procedure name.
- **Previous Recovery**: Recorded self-healing adaptation (e.g. `"Download" → "Export Report"`).
- **Last Verified**: Status of last human/automated verification.
- **Confidence Meter**: Visual gradient bar showing score from `0.00` to `1.00`.

### 6. Workflow Engine Panel
- **Workflow Name & Version**: Active procedure identifier.
- **Execution Mode**: `Deterministic`, `Adaptive`, or `Agentic`.
- **Run Metrics**: Count of successful runs vs. recovery runs.

### 7. Recovery & Self-Healing Panel
Visible during execution and failure adaptation:
- **Expected**: Target element or state.
- **Observed**: Divergence or error code.
- **Recovery Action**: Strategy applied (`Re-observe DOM → Semantic ARIA locator adaptation` or `Global Replan`).
- **Recovery Status**: Real-time status badge.

### 8. Checkpoint & Resume Panel
- **Latest Checkpoint ID**: Atomic snapshot identifier.
- **Trigger**: Checkpoint boundary trigger (e.g. `PRE_HUMAN_VERIFICATION`).
- **State Hash**: Canonical SHA-256 integrity hash.
- **Environment Status**: `VALID (Atomic Snapshot)`.
- **Resume Status**: `AVAILABLE (Resumable at gate)`.

### 9. Security & Policy Panel
- **Policy Status**: `ACTIVE (Rules Enforced)`.
- **Credential Vault**: `Available through secure reference`.
- **Raw Secrets**: `Never displayed (Redacted)`.
- **Action Risk**: `LOW`, `MEDIUM`, or `HIGH`.
- **Authority Boundary**: Confirms human verification is outside LLM authority (Trust Domain T0).

### 10. Live Event Stream & Audit Log
- Chronological, auto-scrolling log with timestamps, event types (`StepStarted`, `ObservationCaptured`, `VerificationEvaluated`, `HumanVerificationRequested`, etc.), and structured payload data.

---

## 4. REST API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves dashboard Single-Page Application |
| `GET` | `/api/health` | Healthcheck and runtime version |
| `POST` | `/api/executions` | Submit new task (`{"task": str, "auto_confirm": bool}`) |
| `GET` | `/api/executions` | List recent executions |
| `GET` | `/api/executions/{id}` | Execution details, human verification status, checkpoints |
| `POST` | `/api/executions/{id}/confirm` | Confirm execution at human gate (`{"verified_by": str}`) |
| `POST` | `/api/executions/{id}/reject` | Reject execution at human gate (`{"reason": str, "verified_by": str}`) |
| `POST` | `/api/executions/{id}/cancel` | Cancel active execution |
| `GET` | `/api/executions/{id}/events` | Historical domain events for execution |
| `GET` | `/api/executions/{id}/checkpoints` | Checkpoints associated with execution |
| `GET` | `/api/memory` | Query experiential memory items |
| `GET` | `/api/security` | Query policy and vault security status |

---

## 5. WebSocket Event Protocol

### Endpoint:
```text
ws://127.0.0.1:8000/ws/executions/{execution_id}
```

### Event Payload Structure:
```json
{
  "type": "event",
  "event": {
    "event_id": "97223b5d-e009-4bf7-a365-9273c52e825a",
    "execution_id": "e5c66349-9378-47c8-8f49-6114266035af",
    "event_type": "HumanVerificationRequested",
    "sequence_number": 5,
    "timestamp": "2026-09-12T07:24:10.304521Z",
    "payload": {
      "task_id": "de9655fd-ba7b-45fe-80d7-7938d7ad9fed",
      "status": "pending"
    }
  },
  "execution": {
    "id": "e5c66349-9378-47c8-8f49-6114266035af",
    "status": "awaiting_human_verification",
    "human_verification": {
      "required": true,
      "status": "pending"
    }
  },
  "checkpoints": [ ... ]
}
```
Client may send `{"type": "ping"}` to receive `{"type": "pong"}` heartbeats.
