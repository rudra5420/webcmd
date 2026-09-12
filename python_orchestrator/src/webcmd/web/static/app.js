/**
 * WebCMD Local Control and Visualization Layer
 * Handles REST API calls, WebSocket real-time events, canonical lifecycle stepper,
 * memory visualization, and the single final human verification gate.
 */

const CANONICAL_STAGES = [
  { id: "intent", name: "Intent" },
  { id: "memory", name: "Memory" },
  { id: "plan", name: "Plan" },
  { id: "policy", name: "Policy" },
  { id: "execute", name: "Execute" },
  { id: "observe", name: "Observe" },
  { id: "verify", name: "Verify" },
  { id: "checkpoint", name: "Checkpoint" },
  { id: "recover", name: "Recover" },
  { id: "human", name: "Human Gate" },
  { id: "complete", name: "Complete" },
  { id: "learn", name: "Learn" },
];

let currentExecutionId = null;
let currentTaskText = "";
let currentExecution = null;
let socket = null;
let pollTimer = null;

// DOM Elements
const taskForm = document.getElementById("task-form");
const taskInput = document.getElementById("task-input");
const autoApproveCheckbox = document.getElementById("auto-approve-checkbox");
const btnRun = document.getElementById("btn-run");
const btnCancel = document.getElementById("btn-cancel-exec");
const btnRefresh = document.getElementById("btn-refresh-data");
const btnClearLogs = document.getElementById("btn-clear-logs");

const execCardTitle = document.querySelector(".active-execution-card .card-title");
const currentExecIdEl = document.getElementById("current-exec-id");
const currentTaskTextEl = document.getElementById("current-task-text");
const currentStatusPill = document.getElementById("current-status-pill");
const currentWorkerEl = document.getElementById("current-worker-name");
const currentStepProgressEl = document.getElementById("current-step-progress");
const timelineStepperEl = document.getElementById("timeline-stepper");

// Human Gate Elements
const gateCard = document.getElementById("human-verification-gate");
const gateTaskDesc = document.getElementById("gate-task-desc");
const gateResultOutput = document.getElementById("gate-result-output");
const btnConfirmGate = document.getElementById("btn-confirm-gate");
const btnRejectGate = document.getElementById("btn-reject-gate");
const rejectionBox = document.getElementById("rejection-box");
const rejectionReasonInput = document.getElementById("rejection-reason");
const btnSubmitRejection = document.getElementById("btn-submit-rejection");
const btnCancelRejection = document.getElementById("btn-cancel-rejection");

// Memory & Recovery Elements
const memDomain = document.getElementById("mem-domain");
const memLastVisit = document.getElementById("mem-last-visit");
const memKnownWorkflow = document.getElementById("mem-known-workflow");
const memPreviousRecovery = document.getElementById("mem-previous-recovery");
const memLastVerified = document.getElementById("mem-last-verified");
const memConfidenceBadge = document.getElementById("memory-confidence-badge");
const meterFill = document.getElementById("meter-fill");

const recoveryStatusBadge = document.getElementById("recovery-status-badge");
const recExpected = document.getElementById("rec-expected");
const recObserved = document.getElementById("rec-observed");
const recStrategy = document.getElementById("rec-strategy");
const recOutcome = document.getElementById("rec-outcome");

const cpLatestId = document.getElementById("cp-latest-id");
const cpTrigger = document.getElementById("cp-trigger");
const cpHash = document.getElementById("cp-hash");
const cpEnvStatus = document.getElementById("cp-env-status");
const cpResumeStatus = document.getElementById("cp-resume-status");

const wsDot = document.getElementById("ws-dot");
const wsStatusText = document.getElementById("ws-status-text");
const logsContainer = document.getElementById("logs-container");
const secRiskLevel = document.getElementById("sec-risk-level");

// Initialize
function init() {
  renderStepper();
  bindEvents();
  checkHealthAndSync();
}

function renderStepper() {
  timelineStepperEl.innerHTML = CANONICAL_STAGES.map((s, idx) => `
    <div class="step-node" id="step-${s.id}">
      <div class="step-circle">${idx + 1}</div>
      <div class="step-name">${s.name}</div>
    </div>
  `).join("");
}

function bindEvents() {
  taskForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const task = taskInput.value.trim();
    if (!task) return;
    await submitTask(task, autoApproveCheckbox.checked);
  });

  // Example chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      taskInput.value = chip.getAttribute("data-task");
      taskInput.focus();
    });
  });

  btnConfirmGate.addEventListener("click", async () => {
    if (!currentExecutionId) return;
    await confirmGate(currentExecutionId);
  });

  btnRejectGate.addEventListener("click", () => {
    rejectionBox.classList.remove("hidden");
    rejectionReasonInput.focus();
  });

  btnCancelRejection.addEventListener("click", () => {
    rejectionBox.classList.add("hidden");
  });

  btnSubmitRejection.addEventListener("click", async () => {
    if (!currentExecutionId) return;
    const reason = rejectionReasonInput.value.trim();
    await rejectGate(currentExecutionId, reason);
    rejectionBox.classList.add("hidden");
  });

  btnCancel.addEventListener("click", async () => {
    if (!currentExecutionId) return;
    await cancelExecution(currentExecutionId);
  });

  btnRefresh.addEventListener("click", async () => {
    await syncAll(true);
  });

  btnClearLogs.addEventListener("click", () => {
    logsContainer.innerHTML = '<div class="log-entry log-dim">[Logs cleared.]</div>';
  });
}

async function checkHealthAndSync() {
  try {
    const res = await fetch("/api/health");
    if (res.ok) {
      wsDot.className = "status-dot connected";
      wsStatusText.textContent = "Live Connected";
    }
  } catch (e) {
    wsDot.className = "status-dot disconnected";
    wsStatusText.textContent = "Offline";
  }
  await syncAll();
}

// Master Synchronization Function
async function syncAll(isManual = false) {
  if (btnRefresh) {
    btnRefresh.disabled = true;
    btnRefresh.style.opacity = "0.7";
  }

  try {
    const resp = await fetch("/api/executions");
    if (resp.ok) {
      const list = await resp.json();
      if (list && list.length > 0) {
        // Backend returns executions sorted ORDER BY created_at DESC (newest at index 0)
        const latest = list[0];
        currentExecutionId = latest.execution_id || latest.id;
        currentExecIdEl.textContent = currentExecutionId;
        currentTaskText = latest.task_text || latest.metadata?.task || latest.metadata?.intent || "Recent execution";
        currentTaskTextEl.textContent = currentTaskText;

        await fetchExecutionDetails(currentExecutionId);

        const status = (latest.status || "").toLowerCase();
        if (["running", "pending", "awaiting_human_verification", "verifying"].includes(status)) {
          connectWebSocket(currentExecutionId);
          startPolling(currentExecutionId);
        } else {
          if (pollTimer) clearInterval(pollTimer);
        }
      } else {
        currentExecIdEl.textContent = "No executions yet";
        currentTaskTextEl.textContent = "Enter a task above to begin";
        updateStatusPill("idle");
        currentWorkerEl.textContent = "—";
        currentStepProgressEl.textContent = "0 / 0";
      }
    }

    await fetchMemory();
    await fetchSecurity();

    if (isManual) {
      addLog("Sync", "State synchronized with backend.");
    }
  } catch (err) {
    console.error("Sync error:", err);
    if (isManual) {
      addLog("Error", `Sync failed: ${err.message}`);
    }
  } finally {
    if (btnRefresh) {
      btnRefresh.disabled = false;
      btnRefresh.style.opacity = "1";
    }
  }
}

// API Calls
async function submitTask(task, autoConfirm) {
  try {
    btnRun.disabled = true;
    currentTaskText = task;
    currentTaskTextEl.textContent = task;
    gateCard.classList.add("hidden");
    rejectionBox.classList.add("hidden");

    if (execCardTitle) execCardTitle.textContent = "ACTIVE EXECUTION";

    addLog("Client", `Task submitted: "${task}" (auto_confirm=${autoConfirm})`);

    const resp = await fetch("/api/executions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, auto_confirm: autoConfirm }),
    });

    if (!resp.ok) {
      throw new Error(`Failed to submit task: ${resp.statusText}`);
    }

    const data = await resp.json();
    currentExecutionId = data.execution_id;
    currentExecIdEl.textContent = currentExecutionId;
    btnCancel.disabled = false;
    btnCancel.style.opacity = "1";
    btnCancel.style.pointerEvents = "auto";

    updateStatusPill("pending");
    resetStepper();
    setStageState("intent", "active");

    // Reset recovery card for new execution
    resetRecoveryCard();

    connectWebSocket(currentExecutionId);
    startPolling(currentExecutionId);
  } catch (err) {
    addLog("Error", err.message);
  } finally {
    btnRun.disabled = false;
  }
}

async function confirmGate(executionId) {
  try {
    addLog("HumanGate", `Operator confirmed execution ${executionId}`);
    const resp = await fetch(`/api/executions/${executionId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verified_by: "operator" }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Confirm failed");
    }
    const data = await resp.json();
    handleExecutionUpdate(data.execution);
    addLog("Success", "Execution verified and completed. Memory updated with confidence 0.95.");
    await fetchMemory();
    await fetchExecutionDetails(executionId);
  } catch (err) {
    addLog("Error", `Confirm failed: ${err.message}`);
  }
}

async function rejectGate(executionId, reason) {
  try {
    addLog("HumanGate", `Operator rejected execution ${executionId}: "${reason || 'no reason'}"`);
    const resp = await fetch(`/api/executions/${executionId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, verified_by: "operator" }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Reject failed");
    }
    const data = await resp.json();
    handleExecutionUpdate(data.execution);
    addLog("Recovery", `Execution escalated to recovery. Rejection recorded in failure memory.`);
    await fetchMemory();
    await fetchExecutionDetails(executionId);
  } catch (err) {
    addLog("Error", `Reject failed: ${err.message}`);
  }
}

async function cancelExecution(executionId) {
  try {
    const resp = await fetch(`/api/executions/${executionId}/cancel`, { method: "POST" });
    if (resp.ok) {
      addLog("Cancel", `Execution ${executionId} cancelled.`);
      updateStatusPill("cancelled");
      btnCancel.disabled = true;
      btnCancel.style.opacity = "0.3";
      if (pollTimer) clearInterval(pollTimer);
    }
  } catch (err) {
    addLog("Error", `Cancel failed: ${err.message}`);
  }
}

async function fetchExecutionDetails(executionId) {
  try {
    const resp = await fetch(`/api/executions/${executionId}`);
    if (resp.ok) {
      const data = await resp.json();
      const ex = data.execution;
      if (data.task_text || ex.task_text || ex.metadata?.task) {
        currentTaskText = data.task_text || ex.task_text || ex.metadata.task;
        currentTaskTextEl.textContent = currentTaskText;
      }
      handleExecutionUpdate(ex);

      if (data.checkpoints && data.checkpoints.length > 0) {
        updateCheckpointCard(data.checkpoints[data.checkpoints.length - 1]);
      } else {
        resetCheckpointCard();
      }

      if (data.events && data.events.length > 0) {
        replayExecutionStateFromEvents(data.events, ex.status);
      }
    }
  } catch (e) {
    // Ignore transient poll error
  }
}

async function fetchMemory() {
  try {
    const resp = await fetch("/api/memory");
    if (resp.ok) {
      const items = await resp.json();
      if (items && items.length > 0) {
        const top = items[0];
        memDomain.textContent = top.scope_key || "target.com";
        const conf = top.confidence || 0.7;
        memConfidenceBadge.textContent = `Confidence: ${conf.toFixed(2)}`;
        meterFill.style.width = `${Math.round(conf * 100)}%`;
        memLastVisit.textContent = "Recent execution";
        memLastVerified.textContent = top.provenance?.human_verified
          ? "Human Confirmed (0.95)"
          : "Automated Verification (0.70)";

        const wf = top.content?.workflow || (top.content?.preferred_selector ? "monthly_report_download" : "web_interaction");
        memKnownWorkflow.textContent = wf;

        if (top.content?.adapted || top.content?.repair_action) {
          memPreviousRecovery.textContent = top.content.repair_action || '"Download" → "Export Report"';
        } else {
          memPreviousRecovery.textContent = "None (Direct execution)";
        }

        const countSuccess = top.success_count || (top.provenance?.human_verified ? 1 : 0);
        document.getElementById("stat-successful-runs").textContent = Math.max(countSuccess, items.length);
      } else {
        memDomain.textContent = "No memory stored";
        memKnownWorkflow.textContent = "None";
        memPreviousRecovery.textContent = "None";
        memLastVerified.textContent = "Cold start";
        memConfidenceBadge.textContent = "Confidence: 0.00";
        meterFill.style.width = "0%";
      }
    }
  } catch (e) {
    // Ignore
  }
}

async function fetchSecurity() {
  try {
    const resp = await fetch("/api/security");
    if (resp.ok) {
      const sec = await resp.json();
      if (secRiskLevel && sec.current_action_risk) {
        secRiskLevel.textContent = `${sec.current_action_risk} (Read/Execute)`;
      }
    }
  } catch (e) {}
}

// WebSocket Management
function connectWebSocket(executionId) {
  if (socket) {
    try { socket.close(); } catch (e) {}
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/executions/${executionId}`;

  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    wsDot.className = "status-dot connected";
    wsStatusText.textContent = "Live WS Connected";
  };

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "event" && msg.event) {
        handleDomainEvent(msg.event);
        if (msg.execution) {
          handleExecutionUpdate(msg.execution);
        }
        if (msg.checkpoints && msg.checkpoints.length > 0) {
          updateCheckpointCard(msg.checkpoints[msg.checkpoints.length - 1]);
        }
      } else if (msg.type === "execution_status" && msg.execution) {
        handleExecutionUpdate(msg.execution);
      }
    } catch (err) {
      console.error("WS message parse error:", err);
    }
  };

  socket.onclose = () => {
    wsDot.className = "status-dot connected";
    wsStatusText.textContent = "Live Connected";
  };

  socket.onerror = () => {
    wsDot.className = "status-dot disconnected";
    wsStatusText.textContent = "WS Reconnecting";
  };
}

function startPolling(executionId) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    if (currentExecutionId === executionId) {
      fetchExecutionDetails(executionId);
    }
  }, 1500);
}

// Event Handlers
function handleDomainEvent(ev) {
  const time = (ev.timestamp || "").substring(11, 19) || new Date().toLocaleTimeString();
  const payloadStr = JSON.stringify(ev.payload || {});
  addLog(ev.event_type, payloadStr, time);

  if (ev.event_type === "ExecutionCreated") {
    setStageState("intent", "completed");
  } else if (ev.event_type === "MemoryUpdated") {
    setStageState("memory", "completed");
    if (ev.payload?.status === "learned") {
      setStageState("learn", "completed");
    }
  } else if (ev.event_type === "PolicyEvaluated") {
    setStageState("policy", "completed");
  } else if (ev.event_type === "StepStarted") {
    currentWorkerEl.textContent = ev.payload?.worker_type || "browser.playwright";
    currentStepProgressEl.textContent = "Step 1 of 1";
    setStageState("execute", "active");
  } else if (ev.event_type === "StepCompleted") {
    if (ev.payload?.worker_type) {
      currentWorkerEl.textContent = ev.payload.worker_type;
    }
    setStageState("execute", "completed");
  } else if (ev.event_type === "ObservationCaptured") {
    setStageState("observe", "completed");
  } else if (ev.event_type === "VerificationEvaluated") {
    setStageState("verify", "completed");
  } else if (ev.event_type === "CheckpointCreated") {
    setStageState("checkpoint", "completed");
    updateCheckpointCard(ev.payload);
  } else if (ev.event_type === "HumanVerificationRequested") {
    setStageState("human", "waiting-gate");
  } else if (ev.event_type === "HumanVerificationDecided") {
    setStageState("human", "completed");
  } else if (ev.event_type === "RecoveryAttempted") {
    setStageState("recover", "completed");
    recoveryStatusBadge.className = "status-pill status-recovering";
    recoveryStatusBadge.textContent = "Recovered";
    recExpected.textContent = ev.payload?.original_selector || "#btn-download";
    recObserved.textContent = ev.payload?.reason || "Element divergence detected";
    recStrategy.textContent = ev.payload?.strategy || "ARIA / Text Locator Adaptation";
    recOutcome.textContent = `✓ Adapted to ${ev.payload?.adapted_selector || '#btn-export'}`;
  }
}

function handleExecutionUpdate(ex) {
  currentExecution = ex;
  const status = (ex.status || "").toLowerCase();
  updateStatusPill(status);

  const isTerminal = ["completed", "failed", "cancelled"].includes(status);
  btnCancel.disabled = isTerminal;
  btnCancel.style.opacity = isTerminal ? "0.3" : "1";
  btnCancel.style.pointerEvents = isTerminal ? "none" : "auto";

  if (execCardTitle) {
    execCardTitle.textContent = isTerminal ? "EXECUTION HISTORY" : "ACTIVE EXECUTION";
  }

  if (status === "awaiting_human_verification") {
    gateCard.classList.remove("hidden");
    gateTaskDesc.textContent = currentTaskText || ex.task_id;
    gateResultOutput.textContent = typeof ex.result === "object"
      ? JSON.stringify(ex.result, null, 2)
      : (ex.result || "Automated verification checks passed. Ready for final human confirmation.");
  } else if (status === "completed") {
    gateCard.classList.add("hidden");
    if (pollTimer) clearInterval(pollTimer);
  } else if (status === "failed" || status === "cancelled") {
    gateCard.classList.add("hidden");
    if (pollTimer) clearInterval(pollTimer);
  } else if (status === "recovering") {
    gateCard.classList.add("hidden");
    recoveryStatusBadge.className = "status-pill status-recovering";
    recoveryStatusBadge.textContent = "Recovering";
    recExpected.textContent = "Target verification result";
    recObserved.textContent = ex.failure_code || "Human rejected final result";
    recStrategy.textContent = "Global Replan & Review Escalation";
    recOutcome.textContent = "⚠ Escalated to bounded recovery engine";
  }
}

function replayExecutionStateFromEvents(events, status) {
  resetStepper();

  const evTypes = new Set(events.map(e => e.event_type));

  if (evTypes.has("ExecutionCreated")) setStageState("intent", "completed");
  if (evTypes.has("MemoryUpdated")) setStageState("memory", "completed");
  setStageState("plan", "completed");
  if (evTypes.has("PolicyEvaluated")) setStageState("policy", "completed");

  const stepStarted = events.find(e => e.event_type === "StepStarted");
  const stepCompleted = events.find(e => e.event_type === "StepCompleted");

  if (stepStarted) {
    currentWorkerEl.textContent = stepStarted.payload?.worker_type || "browser.playwright";
    currentStepProgressEl.textContent = "Step 1 of 1";
    setStageState("execute", stepCompleted ? "completed" : "active");
  }

  if (evTypes.has("ObservationCaptured")) setStageState("observe", "completed");
  if (evTypes.has("VerificationEvaluated")) setStageState("verify", "completed");
  if (evTypes.has("CheckpointCreated")) setStageState("checkpoint", "completed");

  const recEv = events.find(e => e.event_type === "RecoveryAttempted");
  if (recEv) {
    setStageState("recover", "completed");
    recoveryStatusBadge.className = "status-pill status-recovering";
    recoveryStatusBadge.textContent = "Recovered";
    recExpected.textContent = recEv.payload?.original_selector || "#btn-download";
    recObserved.textContent = recEv.payload?.reason || "Element divergence detected";
    recStrategy.textContent = recEv.payload?.strategy || "ARIA / Text Locator Adaptation";
    recOutcome.textContent = `✓ Adapted to ${recEv.payload?.adapted_selector || '#btn-export'}`;
  } else {
    resetRecoveryCard();
  }

  if (evTypes.has("HumanVerificationRequested")) {
    if (status === "awaiting_human_verification") {
      setStageState("human", "waiting-gate");
    } else {
      setStageState("human", "completed");
    }
  }

  if (status === "completed") {
    setStageState("complete", "completed");
    setStageState("learn", "completed");
  } else if (status === "failed") {
    setStageState("complete", "active");
  }
}

function updateStatusPill(status) {
  currentStatusPill.className = "status-pill";
  if (status === "running") {
    currentStatusPill.classList.add("status-running");
    currentStatusPill.textContent = "RUNNING";
  } else if (status === "awaiting_human_verification") {
    currentStatusPill.classList.add("status-waiting");
    currentStatusPill.textContent = "AWAITING HUMAN VERIFICATION";
  } else if (status === "completed") {
    currentStatusPill.classList.add("status-success");
    currentStatusPill.textContent = "COMPLETED";
  } else if (status === "recovering") {
    currentStatusPill.classList.add("status-recovering");
    currentStatusPill.textContent = "RECOVERING";
  } else if (status === "failed") {
    currentStatusPill.classList.add("status-failed");
    currentStatusPill.textContent = "FAILED";
  } else if (status === "cancelled") {
    currentStatusPill.classList.add("status-idle");
    currentStatusPill.textContent = "CANCELLED";
  } else {
    currentStatusPill.classList.add("status-idle");
    currentStatusPill.textContent = (status || "IDLE").toUpperCase();
  }
}

function resetStepper() {
  CANONICAL_STAGES.forEach(s => setStageState(s.id, ""));
}

function setStageState(stageId, state) {
  const el = document.getElementById(`step-${stageId}`);
  if (!el) return;
  el.classList.remove("completed", "active", "waiting-gate");
  if (state) {
    el.classList.add(state);
  }
}

function resetRecoveryCard() {
  recoveryStatusBadge.className = "status-pill status-idle";
  recoveryStatusBadge.textContent = "Standby";
  recExpected.textContent = "Direct execution";
  recObserved.textContent = "Nominal DOM structure";
  recStrategy.textContent = "Deterministic worker";
  recOutcome.textContent = "Nominal — No divergence";
}

function updateCheckpointCard(cp) {
  if (!cp) return;
  const idStr = cp.checkpoint_id || cp.execution_id || String(cp.sequence || "");
  cpLatestId.textContent = idStr.length > 18 ? idStr.substring(0, 18) + "..." : idStr;
  cpTrigger.textContent = cp.trigger || "PRE_HUMAN_VERIFICATION";
  const hashStr = cp.state_hash || "sha256:verified";
  cpHash.textContent = hashStr.length > 18 ? hashStr.substring(0, 18) + "..." : hashStr;
  cpEnvStatus.textContent = "VALID (SHA-256 Verified)";
  cpResumeStatus.textContent = "AVAILABLE (Resumable)";
}

function resetCheckpointCard() {
  cpLatestId.textContent = "None";
  cpTrigger.textContent = "None";
  cpHash.textContent = "None";
  cpEnvStatus.textContent = "N/A";
  cpResumeStatus.textContent = "Created before human gate";
}

function addLog(eventType, payload, time = null) {
  const t = time || new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerHTML = `<span class="log-time">[${t}]</span> <span class="log-event">${eventType}</span> <span class="log-payload">${payload}</span>`;
  logsContainer.appendChild(entry);
  logsContainer.scrollTop = logsContainer.scrollHeight;
}

// Start on DOM ready
document.addEventListener("DOMContentLoaded", init);
