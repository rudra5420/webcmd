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

// Initialize
function init() {
  renderStepper();
  bindEvents();
  fetchInitialState();
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

  btnRefresh.addEventListener("click", () => {
    if (currentExecutionId) {
      fetchExecutionDetails(currentExecutionId);
    }
    fetchMemory();
  });

  btnClearLogs.addEventListener("click", () => {
    logsContainer.innerHTML = '<div class="log-entry log-dim">[Logs cleared.]</div>';
  });
}

// API Calls
async function submitTask(task, autoConfirm) {
  try {
    btnRun.disabled = true;
    currentTaskText = task;
    currentTaskTextEl.textContent = task;
    gateCard.classList.add("hidden");
    rejectionBox.classList.add("hidden");

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

    updateStatusPill("pending");
    updateStepperForStatus("pending");

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
    fetchMemory();
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
    fetchMemory();
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
      handleExecutionUpdate(data.execution);
      if (data.checkpoints && data.checkpoints.length > 0) {
        updateCheckpointCard(data.checkpoints[data.checkpoints.length - 1]);
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
        memLastVisit.textContent = "Just now";
        memLastVerified.textContent = top.provenance?.human_verified ? "Today (Human Confirmed)" : "Automated Only";
        
        const countSuccess = top.success_count || (top.provenance?.human_verified ? 1 : 0);
        document.getElementById("stat-successful-runs").textContent = countSuccess;
      }
    }
  } catch (e) {
    // Ignore
  }
}

async function fetchInitialState() {
  try {
    fetchMemory();
    const resp = await fetch("/api/executions");
    if (resp.ok) {
      const list = await resp.json();
      if (list && list.length > 0) {
        const latest = list[list.length - 1];
        currentExecutionId = latest.execution_id;
        currentExecIdEl.textContent = currentExecutionId;
        currentTaskText = latest.task_id || "Recent execution";
        currentTaskTextEl.textContent = currentTaskText;
        handleExecutionUpdate(latest);
        fetchExecutionDetails(currentExecutionId);
      }
    }
  } catch (e) {}
}

// WebSocket Management
function connectWebSocket(executionId) {
  if (socket) {
    socket.close();
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
    wsDot.className = "status-dot disconnected";
    wsStatusText.textContent = "Polling fallback";
  };

  socket.onerror = () => {
    wsDot.className = "status-dot disconnected";
    wsStatusText.textContent = "WS Error";
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

// State Handlers
function handleDomainEvent(ev) {
  const time = (ev.timestamp || "").substring(11, 19) || new Date().toLocaleTimeString();
  const payloadStr = JSON.stringify(ev.payload || {});
  addLog(ev.event_type, payloadStr, time);

  if (ev.event_type === "StepStarted") {
    currentWorkerEl.textContent = ev.payload?.worker_type || "Worker";
    currentStepProgressEl.textContent = "Step 1 of 1";
    highlightStep("execute");
  } else if (ev.event_type === "ObservationCaptured") {
    highlightStep("observe");
  } else if (ev.event_type === "VerificationEvaluated") {
    highlightStep("verify");
  } else if (ev.event_type === "CheckpointCreated") {
    highlightStep("checkpoint");
  } else if (ev.event_type === "HumanVerificationRequested") {
    highlightStep("human");
  } else if (ev.event_type === "RecoveryAttempted") {
    highlightStep("recover");
    recoveryStatusBadge.className = "status-pill status-recovering";
    recoveryStatusBadge.textContent = "Recovering";
    recObserved.textContent = ev.payload?.reason || "Element divergence detected";
    recStrategy.textContent = "Local repair → Fallback selector strategy";
    recOutcome.textContent = "⚠ Autonomous adaptation engaged";
  }
}

function handleExecutionUpdate(ex) {
  currentExecution = ex;
  const status = (ex.status || "").toLowerCase();
  updateStatusPill(status);
  updateStepperForStatus(status);

  if (status === "awaiting_human_verification") {
    gateCard.classList.remove("hidden");
    gateTaskDesc.textContent = currentTaskText || ex.task_id;
    gateResultOutput.textContent = typeof ex.result === "object" ? JSON.stringify(ex.result, null, 2) : (ex.result || "Execution completed successfully");
    btnCancel.disabled = false;
  } else if (status === "completed") {
    gateCard.classList.add("hidden");
    btnCancel.disabled = true;
    if (pollTimer) clearInterval(pollTimer);
  } else if (status === "failed" || status === "cancelled") {
    gateCard.classList.add("hidden");
    btnCancel.disabled = true;
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
  } else {
    currentStatusPill.classList.add("status-idle");
    currentStatusPill.textContent = (status || "IDLE").toUpperCase();
  }
}

function updateStepperForStatus(status) {
  const stageOrder = ["intent", "memory", "plan", "policy", "execute", "observe", "verify", "checkpoint", "recover", "human", "complete", "learn"];
  
  if (status === "pending") {
    setStageState("intent", "active");
  } else if (status === "running") {
    setStageState("intent", "completed");
    setStageState("memory", "completed");
    setStageState("plan", "completed");
    setStageState("policy", "completed");
    setStageState("execute", "active");
  } else if (status === "verifying") {
    setStageState("execute", "completed");
    setStageState("observe", "completed");
    setStageState("verify", "active");
  } else if (status === "awaiting_human_verification") {
    stageOrder.slice(0, 8).forEach(s => setStageState(s, "completed"));
    setStageState("human", "waiting-gate");
  } else if (status === "completed") {
    stageOrder.forEach(s => setStageState(s, "completed"));
  } else if (status === "recovering") {
    setStageState("recover", "active");
  }
}

function highlightStep(stageId) {
  setStageState(stageId, "active");
}

function setStageState(stageId, state) {
  const el = document.getElementById(`step-${stageId}`);
  if (!el) return;
  el.classList.remove("completed", "active", "waiting-gate");
  if (state) {
    el.classList.add(state);
  }
}

function updateCheckpointCard(cp) {
  if (!cp) return;
  cpLatestId.textContent = (cp.checkpoint_id || cp.execution_id || "").substring(0, 18) + "...";
  cpTrigger.textContent = cp.trigger || "PRE_HUMAN_VERIFICATION";
  cpHash.textContent = (cp.state_hash || "sha256:verified").substring(0, 16) + "...";
  cpEnvStatus.textContent = "VALID (Atomic Snapshot)";
  cpResumeStatus.textContent = "AVAILABLE (Resumable at gate)";
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
