<p align="center">
  <img width="1280" height="420" alt="WebCMD - AI Execution Runtime" src="docs/readme-hero-v2.png" />
</p>

# WebCMD

> **"WebCMD is an AI execution runtime that learns how to perform digital work, verifies the result, and improves from experience."**

WebCMD transforms natural-language instructions into real-world automated browser actions. Unlike brittle scraping scripts or hallucination-prone autonomous agents, WebCMD operates as a **deterministic, verifiable execution runtime** that learns robust navigation patterns, self-heals when websites change, verifies its own postconditions, and gates final execution behind a single human confirmation.

---

## The WebCMD Execution Lifecycle

Every task follows an explicit, audited canonical pipeline:

```text
USER INTENT
    ↓
INTENT NORMALIZATION
    ↓
MEMORY RETRIEVAL (Domain & Experiential Memory)
    ↓
WORKFLOW RESOLUTION
    ↓
HIERARCHICAL PLANNING
    ↓
POLICY CHECK (Hard LLM Boundary & Privilege Check)
    ↓
EXECUTION ROUTER
    ↓
WORKER EXECUTION (Real Headed Chromium via Playwright)
    ↓
OBSERVATION CAPTURE (DOM & Viewport Snapshot)
    ↓
AUTOMATED VERIFICATION (Independent Postcondition Checks)
    ↓
ATOMIC CHECKPOINT (PRE_HUMAN_VERIFICATION)
    ↓
RECOVERY IF DIVERGENT (Autonomous Selector Adaptation)
    ↓
EXACTLY ONE FINAL HUMAN VERIFICATION GATE
    ↓
EXECUTION COMPLETION
    ↓
EXPERIENTIAL LEARNING (Memory Confidence Update to 0.95)
```

---

## Key Architectural Principles

1. **Real Browser Execution**: Launches real Chromium (headed by default on Windows) with persistent profile storage at `./data/browser-profile/`. No fabricated UI animations or simulated outcomes.
2. **Independent Automated Verification**: Execution success is never decided by the generative LLM itself. Dedicated verification engines inspect download file integrity, HTTP statuses, and DOM state.
3. **Autonomous Self-Healing**: When DOM structure drifts (e.g. `#btn-download` changes to `#btn-export`), WebCMD activates bounded recovery, discovers alternative semantic selectors, adapts, verifies the result, and repairs site memory.
4. **Single Final Human Gate**: Exactly one human confirmation gate is enforced per execution. Once automated verification passes, the runtime transitions to `AWAITING_HUMAN_VERIFICATION`. Confirmation updates experiential memory to confidence `0.95`.
5. **Atomic Checkpoints & State Hash**: Pre-verification state is cryptographically hashed and saved so operations can be resumed without re-running destructive work.
6. **Hard LLM Sandbox**: T0 security authority limits model actions. Sensitive credentials and raw session cookies are strictly isolated and never stored in plain text.

---

## Quick Start (Windows)

### Option A: One-Click Startup Script

WebCMD includes a turnkey PowerShell script that validates prerequisites, initializes local storage directories, spins up the test lab portal, and launches the WebCMD dashboard:

```powershell
.\start-dev.ps1
```

Once running, the interactive dashboard opens automatically at `http://127.0.0.1:8000`.

### Option B: Manual Setup with Astral `uv`

WebCMD requires Python 3.11+ and Node.js 18+.

1. **Install Python dependencies**:
   ```bash
   cd python_orchestrator
   uv sync --extra dev
   ```

2. **Start the local Test Lab portal (Port 9888)**:
   ```bash
   node test-lab/server.mjs
   ```

3. **Start the WebCMD Web Server (Port 8000)**:
   ```bash
   cd python_orchestrator
   uv run webcmd web --port 8000
   ```

4. **Access the Web Dashboard**:
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Flagship Demonstrations

### Flagship Demo 1: Deterministic Reports Portal (Self-Healing & Learning)

Proves WebCMD's core value: graceful recovery from UI divergence, independent verification, and instant memory reuse.

1. **Stage 1 — Baseline Run (Mode A)**:
   - Reset the portal: Click **↻ Reset Demo (Mode A)** in the dashboard control panel.
   - Enter task: `Navigate to http://127.0.0.1:9888/portal/ and download September report`
   - Real Chromium opens, clicks `#btn-download`, downloads `september-report.pdf`, verifies file integrity (>0 bytes, valid PDF header), hits the human gate, and stores memory with confidence 0.95.

2. **Stage 2 — Divergence & Self-Healing (Mode B)**:
   - Switch portal UI: Click **⇄ Switch UI (Mode B)**. The portal replaces `#btn-download` with `#btn-export`.
   - Submit the same task again.
   - Initial `#btn-download` locator fails.
   - **Self-Healing Recovery engages**: WebCMD searches semantic locators, discovers `Export Report` (`#btn-export`), completes download, passes automated verification, and alerts operator for confirmation.
   - Memory is updated with the repaired selector.

3. **Stage 3 — Reusing Learned Memory**:
   - Run the task a third time (still in Mode B).
   - WebCMD checks previous experience, identifies the learned `#btn-export` selector, executes immediately without failure or recovery delay!

You can also run this entire sequence automatically by clicking **⚡ Run 3-Stage Demo** on the dashboard.

---

### Flagship Demo 2: Real-World YouTube Automation

Demonstrates complex dynamic single-page app (SPA) automation on a live external service:

1. Enter task:
   ```text
   Go to YouTube, search for ABC Trek, find AjayRaj video, play it and verify
   ```
2. WebCMD launches headed Chromium:
   - Navigates to `https://www.youtube.com`.
   - Dismisses cookie/consent dialogs if present.
   - Locates search bar, types `ABC Trek`, and presses Enter.
   - Inspects search result DOM, finds video matching creator `AjayRaj`.
   - Clicks video and verifies HTML5 `<video>` playback state (`currentTime > 0` and unpaused).
   - Creates atomic checkpoint and requests final human verification.
   - Upon confirmation, saves `youtube_video_search_and_play` experience to local memory.

---

## Web Dashboard Features

- **Split Workspace Layout**: Left pane contains task inputs, quick example chips, live AI execution narrative, and the single Human Gate banner. Right pane displays the **Live Chromium Viewport** with URL bar and session status.
- **Interactive Canonical Timeline**: 12 stages (`Intent`, `Memory`, `Plan`, `Policy`, `Execute`, `Observe`, `Verify`, `Checkpoint`, `Recover`, `Human Gate`, `Complete`, `Learn`). Click any stage to open the **Stage Detail Drawer** with raw telemetry.
- **Runtime Control Panel**: Single-click buttons for `+ New Task`, `⚡ Run 3-Stage Demo`, `■ Stop`, `▶ Resume Checkpoint`, `✕ Clear Session`, `↻ Reset Demo (Mode A)`, `⇄ Switch UI (Mode B)`, `🗑 Reset Demo Memory`, and `🛡 Reset Browser Profile`.
- **Run History Ledger**: Tabular audit trail showing Run ID, Task Objective, Strategy (Exploration, Recovery, or Learned), Outcome, Verification Status, and Timestamp.
- **Real-Time WebSocket Streaming**: Instant domain event updates and live screencast frames without polling overhead.

---

## Directory Structure

```text
webcmd/
├── data/                       # Local persistent runtime storage (gitignored)
│   ├── browser-profile/        # Real Chromium user data & persistent session cookies
│   ├── downloads/              # Downloaded artifacts (reports, exports)
│   ├── screenshots/            # Live screencast frames & verification captures
│   ├── checkpoints/            # Serialized execution checkpoints
│   └── webcmd.db               # SQLite database (memories, executions, events)
├── python_orchestrator/        # Core WebCMD Python runtime
│   ├── src/webcmd/
│   │   ├── core/               # Orchestrator, lifecycle engine
│   │   ├── memory/             # Experiential & site memory engine
│   │   ├── recovery/           # Self-healing & locator adaptation
│   │   ├── verification/       # Automated verification engines
│   │   ├── workers/            # Playwright, HTTP, filesystem, shell workers
│   │   └── web/                # FastAPI web server, WebSocket, static UI
│   └── tests/                  # Unit and integration test suite
├── test-lab/                   # Local deterministic test portal (Node.js)
├── start-dev.ps1               # Windows one-click launcher
└── README.md                   # System documentation
```

---

## Running the Automated Test Suite

WebCMD includes a 96-test automated suite covering unit, integration, and web API layers:

```bash
cd python_orchestrator
uv run --extra dev pytest tests/
```

All 96 tests validate orchestrator lifecycles, memory storage & confidence degradation, checkpoint serialization & resume, self-healing recovery triggers, security policies, and web server endpoints.

---

## License

Apache 2.0. See [LICENSE](./LICENSE) for details.
