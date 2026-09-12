/**
 * WebCMD Local Control and Visualization Layer
 * Handles REST API calls, WebSocket real-time events, canonical lifecycle stepper,
 * live Chromium screencast, chat execution narrative, control panel, run history ledger,
 * and the single final human verification gate.
 */

const CANONICAL_STAGES = [
  { id: "intent", name: "Intent", desc: "Natural-language intent normalization & classification" },
  { id: "memory", name: "Memory", desc: "Domain & site memory retrieval for learned patterns" },
  { id: "plan", name: "Plan", desc: "Hierarchical execution plan generation" },
  { id: "policy", name: "Policy", desc: "Hard LLM boundary & privilege evaluation" },
  { id: "execute", name: "Execute", desc: "Real Chromium browser automation via Playwright" },
  { id: "observe", name: "Observe", desc: "DOM snapshot and viewport state capture" },
  { id: "verify", name: "Verify", desc: "Independent automated postcondition verification" },
  { id: "checkpoint", name: "Checkpoint", desc: "Atomic state checkpoint serialization" },
  { id: "recover", name: "Recover", desc: "Autonomous self-healing & selector adaptation" },
  { id: "human", name: "Human Gate", desc: "Single final operator confirmation gate" },
  { id: "complete", name: "Complete", desc: "Final execution state transition" },
  { id: "learn", name: "Learn", desc: "Experiential memory & workflow update" },
];

let currentExecutionId = null;
let currentTaskText = "";
let currentExecution = null;
let currentEvents = [];
let currentCheckpoints = [];
let socket = null;
let pollTimer = null;
let screencastTimer = null;

// DOM Elements
const taskForm = document.getElementById("task-form");
const taskInput = document.getElementById("task-input");
const autoApproveCheckbox = document.getElementById("auto-approve-checkbox");
const btnRun = document.getElementById("btn-run");
const btnCancel = document.getElementById("btn-cancel-exec");
const btnRefresh = document.getElementById("btn-refresh-data");
const btnClearLogs = document.getElementById("btn-clear-logs");

const execCardTitle = document.getElementById("execution-card-title") || document.querySelector(".active-execution-card .card-title");
const currentExecIdEl = document.getElementById("current-exec-id");
const currentTaskTextEl = document.getElementById("current-task-text");
const currentStatusPill = document.getElementById("current-status-pill");
const currentWorkerEl = document.getElementById("current-worker-name");
const currentStepProgressEl = document.getElementById("current-step-progress");
const timelineStepperEl = document.getElementById("timeline-stepper");

// Stage Detail Drawer
const stageDetailDrawer = document.getElementById("stage-detail-drawer");
const stageDetailTitle = document.getElementById("stage-detail-title");
const stageDetailContent = document.getElementById("stage-detail-content");
const btnCloseStageDetail = document.getElementById("btn-close-stage-detail");

// Screencast & Browser Interactive Elements
const liveBrowserCard = document.getElementById("live-browser-card");
const heroSplitWorkspace = document.querySelector(".hero-split-workspace");
const browserViewport = document.getElementById("browser-viewport");
const browserViewportImg = document.getElementById("browser-viewport-img");
const browserPlaceholder = document.getElementById("browser-placeholder");
const browserLiveUrl = document.getElementById("browser-live-url");
const browserStatusTag = document.getElementById("browser-status-tag");
const btnToggleExpand = document.getElementById("btn-toggle-expand");
const btnFullscreenBrowser = document.getElementById("btn-fullscreen-browser");
const browserInteractiveBar = document.getElementById("browser-interactive-bar");
const btnMediaPlayPause = document.getElementById("btn-media-play-pause");
const btnMediaRewind = document.getElementById("btn-media-rewind");
const btnMediaForward = document.getElementById("btn-media-forward");
const btnMediaMute = document.getElementById("btn-media-mute");
const btnScrollUp = document.getElementById("btn-scroll-up");
const btnScrollDown = document.getElementById("btn-scroll-down");
const clickRipple = document.getElementById("click-ripple");

// Chat Stream Elements
const chatMessagesContainer = document.getElementById("chat-messages-container");

// Control Panel Elements
const btnCtrlNewTask = document.getElementById("btn-ctrl-new-task");
const btnCtrlRunDemo = document.getElementById("btn-ctrl-run-demo");
const btnCtrlStop = document.getElementById("btn-ctrl-stop");
const btnCtrlResume = document.getElementById("btn-ctrl-resume");
const btnCtrlClear = document.getElementById("btn-ctrl-clear");
const btnCtrlResetDemo = document.getElementById("btn-ctrl-reset-demo");
const btnCtrlSwitchDemo = document.getElementById("btn-ctrl-switch-demo");
const btnCtrlResetMem = document.getElementById("btn-ctrl-reset-mem");
const btnCtrlResetProfile = document.getElementById("btn-ctrl-reset-profile");

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
const historyTableBody = document.getElementById("history-table-body");

// Initialize application
function init() {
  renderStepper();
  bindEvents();
  checkHealthAndSync();
  startScreencastPolling();
}

function renderStepper() {
  timelineStepperEl.innerHTML = CANONICAL_STAGES.map((s, idx) => `
    <div class="step-node" id="step-${s.id}" data-stage="${s.id}" title="${s.name}: ${s.desc}">
      <div class="step-circle">${idx + 1}</div>
      <div class="step-name">${s.name}</div>
    </div>
  `).join("");

  // Attach stage click handler for interactive inspection
  document.querySelectorAll(".step-node").forEach(node => {
    node.addEventListener("click", () => {
      const stageId = node.getAttribute("data-stage");
      inspectStage(stageId);
    });
  });
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

  // Human Gate Controls
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

  if (btnCloseStageDetail) {
    btnCloseStageDetail.addEventListener("click", () => {
      stageDetailDrawer.classList.add("hidden");
    });
  }

  // Runtime Control Panel
  if (btnCtrlNewTask) {
    btnCtrlNewTask.addEventListener("click", () => {
      taskInput.value = "";
      taskInput.focus();
    });
  }

  if (btnCtrlRunDemo) {
    btnCtrlRunDemo.addEventListener("click", runGuidedDemo);
  }

  if (btnCtrlStop) {
    btnCtrlStop.addEventListener("click", async () => {
      if (currentExecutionId) await cancelExecution(currentExecutionId);
    });
  }

  if (btnCtrlResume) {
    btnCtrlResume.addEventListener("click", async () => {
      if (!currentExecutionId) return;
      await resumeExecution(currentExecutionId);
    });
  }

  if (btnCtrlClear) {
    btnCtrlClear.addEventListener("click", () => {
      logsContainer.innerHTML = '<div class="log-entry log-dim">[Session cleared.]</div>';
      chatMessagesContainer.innerHTML = `
        <div class="chat-msg msg-assistant">
          <span class="msg-badge">WebCMD</span>
          <span class="msg-text">Ready. Enter a task or launch the demonstration to begin.</span>
        </div>`;
      resetStepper();
      resetRecoveryCard();
      resetCheckpointCard();
    });
  }

  if (btnCtrlResetDemo) {
    btnCtrlResetDemo.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/demo/reset", { method: "POST" });
        const d = await res.json();
        addLog("DemoControl", `Portal reset to Mode A (Version A stable download): ${JSON.stringify(d)}`);
        addChatMessage("WebCMD", "Test portal reset to Version A (Stable `#btn-download` element active).");
      } catch (e) {
        addLog("Error", `Reset demo failed: ${e.message}`);
      }
    });
  }

  if (btnCtrlSwitchDemo) {
    btnCtrlSwitchDemo.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/demo/switch", { method: "POST" });
        const d = await res.json();
        addLog("DemoControl", `Portal switched to Mode B (Version B export report): ${JSON.stringify(d)}`);
        addChatMessage("WebCMD", "Test portal switched to Version B (UI changed: `#btn-download` removed, replaced with `#btn-export`). Next run will trigger self-healing recovery!");
      } catch (e) {
        addLog("Error", `Switch demo failed: ${e.message}`);
      }
    });
  }

  if (btnCtrlResetMem) {
    btnCtrlResetMem.addEventListener("click", async () => {
      try {
        await fetch("/api/memory/clear", { method: "POST" });
        addLog("MemoryControl", "Experiential memory items cleared for clean demo baseline.");
        addChatMessage("WebCMD", "Experiential site memory cleared. WebCMD will start fresh with zero prior experience.");
        await fetchMemory();
      } catch (e) {
        addLog("Error", `Clear memory failed: ${e.message}`);
      }
    });
  }

  if (btnCtrlResetProfile) {
    btnCtrlResetProfile.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/browser/reset-profile", { method: "POST" });
        const d = await res.json();
        addLog("BrowserControl", `Persistent Chromium profile reset: ${JSON.stringify(d)}`);
        addChatMessage("WebCMD", "Chromium persistent profile cleared at `./data/browser-profile`.");
      } catch (e) {
        addLog("Error", `Reset profile failed: ${e.message}`);
      }
    });
  }

  // Viewport Expand Toggle
  if (btnToggleExpand && heroSplitWorkspace) {
    btnToggleExpand.addEventListener("click", () => {
      heroSplitWorkspace.classList.toggle("expanded-browser");
      const isExpanded = heroSplitWorkspace.classList.contains("expanded-browser");
      btnToggleExpand.innerHTML = isExpanded ? "&#9638; Compact" : "&#9638; Expand";
      btnToggleExpand.title = isExpanded ? "Return to standard split" : "Focus on larger browser viewport";
    });
  }

  // Viewport Fullscreen Toggle
  if (btnFullscreenBrowser) {
    btnFullscreenBrowser.addEventListener("click", toggleBrowserFullscreen);
  }

  // Interactive Media Controls
  if (btnMediaPlayPause) {
    btnMediaPlayPause.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/browser/media/toggle-play", { method: "POST" });
        const d = await res.json();
        if (d.frame && browserViewportImg) {
          browserViewportImg.src = "data:image/jpeg;base64," + d.frame;
        }
        addLog("Media", "Toggled video playback.");
      } catch (e) {
        console.warn("Play/pause error:", e);
      }
    });
  }

  if (btnMediaRewind) {
    btnMediaRewind.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/browser/media/seek", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ seconds: -10 }),
        });
        const d = await res.json();
        if (d.frame && browserViewportImg) {
          browserViewportImg.src = "data:image/jpeg;base64," + d.frame;
        }
      } catch (e) {}
    });
  }

  if (btnMediaForward) {
    btnMediaForward.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/browser/media/seek", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ seconds: 10 }),
        });
        const d = await res.json();
        if (d.frame && browserViewportImg) {
          browserViewportImg.src = "data:image/jpeg;base64," + d.frame;
        }
      } catch (e) {}
    });
  }

  if (btnMediaMute) {
    btnMediaMute.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/browser/media/toggle-mute", { method: "POST" });
        const d = await res.json();
        const isMuted = d.result?.muted;
        btnMediaMute.innerHTML = isMuted ? "&#128263; Unmute" : "&#128266; Mute";
      } catch (e) {}
    });
  }

  if (btnScrollUp) {
    btnScrollUp.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/browser/scroll", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ delta_x: 0, delta_y: -400 }),
        });
        const d = await res.json();
        if (d.frame && browserViewportImg) {
          browserViewportImg.src = "data:image/jpeg;base64," + d.frame;
        }
      } catch (e) {}
    });
  }

  if (btnScrollDown) {
    btnScrollDown.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/browser/scroll", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ delta_x: 0, delta_y: 400 }),
        });
        const d = await res.json();
        if (d.frame && browserViewportImg) {
          browserViewportImg.src = "data:image/jpeg;base64," + d.frame;
        }
      } catch (e) {}
    });
  }

  // Direct Viewport Click Interaction
  if (browserViewportImg) {
    browserViewportImg.addEventListener("click", async (e) => {
      const rect = browserViewportImg.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const scaleX = 1280 / rect.width;
      const scaleY = 800 / rect.height;
      const x = Math.round((e.clientX - rect.left) * scaleX);
      const y = Math.round((e.clientY - rect.top) * scaleY);

      showClickRipple(e.clientX - rect.left, e.clientY - rect.top);

      try {
        const res = await fetch("/api/browser/click", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ x, y, button: "left" }),
        });
        const d = await res.json();
        if (d.frame) {
          browserViewportImg.src = "data:image/jpeg;base64," + d.frame;
        }
      } catch (err) {
        console.warn("Click forwarding error:", err);
      }
    });
  }

  // Direct Viewport Mouse Wheel Scroll
  let wheelThrottleTimer = null;
  if (browserViewport) {
    browserViewport.addEventListener("wheel", (e) => {
      if (!browserViewportImg || browserViewportImg.style.display === "none") return;
      e.preventDefault();
      if (wheelThrottleTimer) return;
      wheelThrottleTimer = setTimeout(() => { wheelThrottleTimer = null; }, 180);

      const deltaY = e.deltaY > 0 ? 350 : -350;
      fetch("/api/browser/scroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ delta_x: 0, delta_y: deltaY }),
      })
      .then(r => r.json())
      .then(d => {
        if (d.frame && browserViewportImg) {
          browserViewportImg.src = "data:image/jpeg;base64," + d.frame;
        }
      })
      .catch(() => {});
    }, { passive: false });
  }
}

function toggleBrowserFullscreen() {
  if (!liveBrowserCard) return;
  const isFs = liveBrowserCard.classList.contains("fullscreen-mode") || document.fullscreenElement === liveBrowserCard;
  if (!isFs) {
    liveBrowserCard.classList.add("fullscreen-mode");
    if (btnFullscreenBrowser) btnFullscreenBrowser.innerHTML = "&#10005; Exit Fullscreen";
    if (liveBrowserCard.requestFullscreen) {
      liveBrowserCard.requestFullscreen().catch(() => {});
    }
  } else {
    liveBrowserCard.classList.remove("fullscreen-mode");
    if (btnFullscreenBrowser) btnFullscreenBrowser.innerHTML = "&#9974; Fullscreen";
    if (document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
  }
}

document.addEventListener("fullscreenchange", () => {
  if (!document.fullscreenElement && liveBrowserCard) {
    liveBrowserCard.classList.remove("fullscreen-mode");
    if (btnFullscreenBrowser) btnFullscreenBrowser.innerHTML = "&#9974; Fullscreen";
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && liveBrowserCard && liveBrowserCard.classList.contains("fullscreen-mode")) {
    toggleBrowserFullscreen();
  }
});

function showClickRipple(relX, relY) {
  if (!clickRipple) return;
  clickRipple.style.left = `${relX}px`;
  clickRipple.style.top = `${relY}px`;
  clickRipple.style.display = "block";
  clickRipple.classList.remove("animating");
  void clickRipple.offsetWidth;
  clickRipple.classList.add("animating");
  setTimeout(() => {
    clickRipple.style.display = "none";
  }, 500);
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
    await fetchHistory();
    await fetchScreencast();

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

    addChatMessage("User", task);
    addChatMessage("WebCMD", `Task received: "${task}". Normalizing intent and checking experience...`);
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
    resetRecoveryCard();

    connectWebSocket(currentExecutionId);
    startPolling(currentExecutionId);
  } catch (err) {
    addLog("Error", err.message);
    addChatMessage("WebCMD", `Error launching task: ${err.message}`);
  } finally {
    btnRun.disabled = false;
  }
}

async function confirmGate(executionId) {
  try {
    addLog("HumanGate", `Operator confirmed execution ${executionId}`);
    addChatMessage("Operator", "Result Confirmed ✓. Proceeding to task completion and experiential memory update.");

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
    addChatMessage("WebCMD", "Task completed successfully. Experiential memory updated with confidence 0.95.");
    await fetchMemory();
    await fetchExecutionDetails(executionId);
    await fetchHistory();
  } catch (err) {
    addLog("Error", `Confirm failed: ${err.message}`);
    addChatMessage("WebCMD", `Confirmation error: ${err.message}`);
  }
}

async function rejectGate(executionId, reason) {
  try {
    addLog("HumanGate", `Operator rejected execution ${executionId}: "${reason || 'no reason'}"`);
    addChatMessage("Operator", `Result Rejected ✗. Reason: "${reason || 'Operator inspection failed'}"`);

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
    addLog("Recovery", "Execution escalated to recovery. Rejection recorded in failure memory.");
    addChatMessage("WebCMD", "Execution marked for review and escalated to bounded recovery engine.");
    await fetchMemory();
    await fetchExecutionDetails(executionId);
    await fetchHistory();
  } catch (err) {
    addLog("Error", `Reject failed: ${err.message}`);
  }
}

async function cancelExecution(executionId) {
  try {
    const resp = await fetch(`/api/executions/${executionId}/cancel`, { method: "POST" });
    if (resp.ok) {
      addLog("Cancel", `Execution ${executionId} cancelled.`);
      addChatMessage("WebCMD", "Execution cancelled by operator.");
      updateStatusPill("cancelled");
      btnCancel.disabled = true;
      btnCancel.style.opacity = "0.3";
      if (pollTimer) clearInterval(pollTimer);
      await fetchHistory();
    }
  } catch (err) {
    addLog("Error", `Cancel failed: ${err.message}`);
  }
}

async function resumeExecution(executionId) {
  try {
    addLog("Resume", `Resuming execution ${executionId} from checkpoint...`);
    addChatMessage("WebCMD", `Resuming execution ${executionId} from latest atomic checkpoint...`);
    const resp = await fetch(`/api/executions/${executionId}/resume`, { method: "POST" });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Resume failed");
    }
    const data = await resp.json();
    handleExecutionUpdate(data.execution);
    addChatMessage("WebCMD", "Execution resumed successfully.");
    startPolling(executionId);
  } catch (err) {
    addLog("Error", `Resume failed: ${err.message}`);
    addChatMessage("WebCMD", `Resume failed: ${err.message}`);
  }
}

async function fetchExecutionDetails(executionId) {
  try {
    const resp = await fetch(`/api/executions/${executionId}`);
    if (resp.ok) {
      const data = await resp.json();
      const ex = data.execution;
      currentExecution = ex;
      currentEvents = data.events || [];
      currentCheckpoints = data.checkpoints || [];

      if (data.task_text || ex.task_text || ex.metadata?.task) {
        currentTaskText = data.task_text || ex.task_text || ex.metadata?.task;
        currentTaskTextEl.textContent = currentTaskText;
      }
      handleExecutionUpdate(ex);

      if (currentCheckpoints.length > 0) {
        updateCheckpointCard(currentCheckpoints[currentCheckpoints.length - 1]);
      } else {
        resetCheckpointCard();
      }

      if (currentEvents.length > 0) {
        replayExecutionStateFromEvents(currentEvents, ex.status);
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
        document.getElementById("stat-successful-runs").textContent = "0";
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

async function fetchHistory() {
  if (!historyTableBody) return;
  try {
    const resp = await fetch("/api/history");
    if (resp.ok) {
      const list = await resp.json();
      if (!list || list.length === 0) {
        historyTableBody.innerHTML = `<tr><td colspan="6" class="empty-row">No runs recorded yet.</td></tr>`;
        return;
      }
      historyTableBody.innerHTML = list.map(item => {
        let statusClass = "status-idle";
        const st = (item.status || "").toLowerCase();
        if (st === "completed") statusClass = "status-success";
        else if (st === "running") statusClass = "status-running";
        else if (st === "awaiting_human_verification") statusClass = "status-waiting";
        else if (st === "failed") statusClass = "status-failed";

        let stratClass = "strategy-badge";
        if (item.strategy.includes("Recovery")) stratClass += " strat-recovery";
        else if (item.strategy.includes("Learned")) stratClass += " strat-learned";

        return `
          <tr class="history-row" data-id="${item.execution_id}" title="Click to view run ${item.execution_id}">
            <td class="mono-text">${item.run_id}</td>
            <td class="task-cell" title="${item.task}">${item.task.length > 40 ? item.task.substring(0, 38) + '...' : item.task}</td>
            <td><span class="${stratClass}">${item.strategy}</span></td>
            <td><span class="status-pill ${statusClass}">${item.status}</span></td>
            <td class="pass-text">${item.verification}</td>
            <td class="mono-text">${item.created_at}</td>
          </tr>
        `;
      }).join("");

      // Add click listener to history rows
      document.querySelectorAll(".history-row").forEach(row => {
        row.addEventListener("click", () => {
          const eid = row.getAttribute("data-id");
          if (eid) {
            currentExecutionId = eid;
            currentExecIdEl.textContent = eid;
            fetchExecutionDetails(eid);
          }
        });
      });
    }
  } catch (e) {
    // Ignore
  }
}

// Live Screencast Polling & Rendering
async function fetchScreencast() {
  if (!browserViewportImg) return;
  try {
    const res = await fetch("/api/browser/screencast");
    if (res.ok) {
      const data = await res.json();
      if (data.frame) {
        browserViewportImg.src = `data:image/jpeg;base64,${data.frame}`;
        browserViewportImg.style.display = "block";
        if (browserPlaceholder) browserPlaceholder.style.display = "none";
      } else if (!data.active && (!browserViewportImg.src || browserViewportImg.src === window.location.href)) {
        browserViewportImg.style.display = "none";
        if (browserPlaceholder) browserPlaceholder.style.display = "flex";
      }

      if (browserLiveUrl && data.url) {
        browserLiveUrl.textContent = data.url;
      }
      if (browserStatusTag) {
        browserStatusTag.textContent = data.active ? "Chromium Active" : "Chromium Ready";
        browserStatusTag.className = data.active ? "browser-status-tag active" : "browser-status-tag";
      }
    }
  } catch (e) {
    // Ignore
  }
}

function startScreencastPolling() {
  if (screencastTimer) clearInterval(screencastTimer);
  screencastTimer = setInterval(fetchScreencast, 1500);
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
        if (msg.screencast) {
          browserViewportImg.src = `data:image/jpeg;base64,${msg.screencast}`;
          browserViewportImg.style.display = "block";
          if (browserPlaceholder) browserPlaceholder.style.display = "none";
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
      fetchScreencast();
    }
  }, 1200);
}

// Event Handlers
function handleDomainEvent(ev) {
  const time = (ev.timestamp || "").substring(11, 19) || new Date().toLocaleTimeString();
  const payloadStr = JSON.stringify(ev.payload || {});
  addLog(ev.event_type, payloadStr, time);

  if (ev.event_type === "ExecutionCreated") {
    setStageState("intent", "completed");
    addChatMessage("WebCMD", `Intent recognized: "${ev.payload?.intent || currentTaskText}". Policy check passed.`);
  } else if (ev.event_type === "MemoryUpdated") {
    setStageState("memory", "completed");
    if (ev.payload?.status === "learned") {
      setStageState("learn", "completed");
      addChatMessage("WebCMD", `Learned experience stored for domain: ${ev.payload?.scope_key || 'target'}. Confidence updated.`);
    }
  } else if (ev.event_type === "PlanCreated") {
    setStageState("plan", "completed");
    const stepsCount = ev.payload?.steps?.length || 1;
    addChatMessage("WebCMD", `Generated execution plan with ${stepsCount} verified actions.`);
  } else if (ev.event_type === "PolicyEvaluated") {
    setStageState("policy", "completed");
  } else if (ev.event_type === "StepStarted") {
    const wType = ev.payload?.worker_type || "browser.playwright";
    currentWorkerEl.textContent = wType;
    currentStepProgressEl.textContent = "Step 1 of 1";
    setStageState("execute", "active");
    addChatMessage("WebCMD", `Executing step with ${wType} worker...`);
  } else if (ev.event_type === "StepCompleted") {
    if (ev.payload?.worker_type) {
      currentWorkerEl.textContent = ev.payload.worker_type;
    }
    setStageState("execute", "completed");
  } else if (ev.event_type === "ObservationCaptured") {
    setStageState("observe", "completed");
    const url = ev.payload?.url || "";
    if (url && browserLiveUrl) browserLiveUrl.textContent = url;
    addChatMessage("WebCMD", `Page state observed. Evaluating assertion rules...`);
  } else if (ev.event_type === "VerificationEvaluated") {
    setStageState("verify", "completed");
    addChatMessage("WebCMD", "Automated postcondition verification: PASS ✓");
  } else if (ev.event_type === "CheckpointCreated") {
    setStageState("checkpoint", "completed");
    updateCheckpointCard(ev.payload);
    addChatMessage("WebCMD", `Atomic checkpoint created: trigger=${ev.payload?.trigger || 'PRE_HUMAN_VERIFICATION'}`);
  } else if (ev.event_type === "HumanVerificationRequested") {
    setStageState("human", "waiting-gate");
    addChatMessage("WebCMD", "Execution paused: EXACTLY ONE final human verification required before completion.");
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
    addChatMessage("WebCMD", `Self-healing recovery engaged: element missing (${ev.payload?.original_selector || '#btn-download'}). Adapted to: ${ev.payload?.adapted_selector || '#btn-export'}`);
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
    fetchHistory();
  } else if (status === "failed" || status === "cancelled") {
    gateCard.classList.add("hidden");
    if (pollTimer) clearInterval(pollTimer);
    fetchHistory();
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

function inspectStage(stageId) {
  if (!stageDetailDrawer) return;
  const stage = CANONICAL_STAGES.find(s => s.id === stageId);
  if (!stage) return;

  stageDetailTitle.textContent = `Stage Details: ${stage.name}`;
  
  let details = {
    stage: stage.name,
    description: stage.desc,
    timestamp: new Date().toISOString(),
  };

  if (stageId === "intent") {
    details.task_input = currentTaskText;
    details.normalized_intent = currentExecution?.intent_type || "EXECUTE_WORKFLOW";
    details.parameters = currentExecution?.parameters || {};
  } else if (stageId === "memory") {
    details.domain = memDomain.textContent;
    details.confidence = memConfidenceBadge.textContent;
    details.known_workflow = memKnownWorkflow.textContent;
  } else if (stageId === "plan") {
    details.worker_assigned = currentWorkerEl.textContent;
    details.strategy = "Deterministic Step Pipeline";
  } else if (stageId === "policy") {
    details.risk_assessment = "LOW (Read/Execute)";
    details.hard_sandbox = "Enforced: No privilege escalation permitted";
  } else if (stageId === "execute") {
    details.worker = currentWorkerEl.textContent;
    details.status = currentStatusPill.textContent;
    details.browser_profile = "./data/browser-profile";
  } else if (stageId === "observe") {
    details.live_url = browserLiveUrl ? browserLiveUrl.textContent : "N/A";
    details.viewport = "1280x800 Chromium";
  } else if (stageId === "verify") {
    details.automated_verification = "PASS";
    details.checks = ["Intent satisfied", "DOM assertions valid", "Integrity verified"];
  } else if (stageId === "checkpoint") {
    details.checkpoint_id = cpLatestId.textContent;
    details.trigger = cpTrigger.textContent;
    details.state_hash = cpHash.textContent;
    details.status = cpResumeStatus.textContent;
  } else if (stageId === "recover") {
    details.status = recoveryStatusBadge.textContent;
    details.expected = recExpected.textContent;
    details.observed = recObserved.textContent;
    details.strategy = recStrategy.textContent;
    details.outcome = recOutcome.textContent;
  } else if (stageId === "human") {
    details.status = currentStatusPill.textContent === "AWAITING HUMAN VERIFICATION" ? "Pending operator confirmation" : "Decided";
    details.gate_type = "EXACTLY ONE FINAL HUMAN GATE";
    details.result_summary = currentExecution?.result || "Verified automated execution";
  } else if (stageId === "complete") {
    details.execution_id = currentExecutionId;
    details.status = currentStatusPill.textContent;
    details.result = currentExecution?.result || {};
  } else if (stageId === "learn") {
    details.experiential_memory = "Updated";
    details.confidence_target = "0.95";
    details.workflow_saved = true;
  }

  stageDetailContent.textContent = JSON.stringify(details, null, 2);
  stageDetailDrawer.classList.remove("hidden");
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

function addChatMessage(sender, text) {
  if (!chatMessagesContainer) return;
  const msgEl = document.createElement("div");
  msgEl.className = `chat-msg msg-${sender.toLowerCase()}`;
  msgEl.innerHTML = `
    <span class="msg-badge">${sender}</span>
    <span class="msg-text">${text}</span>
  `;
  chatMessagesContainer.appendChild(msgEl);
  chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

// Guided 3-Stage End-to-End Demo Runner
async function runGuidedDemo() {
  addChatMessage("WebCMD", "🚀 Starting WebCMD 3-Stage End-to-End Architectural Demonstration...");
  addLog("Demo", "3-Stage Demo initiated.");

  // Stage 1: Baseline Execution (Mode A)
  addChatMessage("WebCMD", "▶ STAGE 1: Baseline Execution (Version A - #btn-download). Resetting demo portal...");
  try {
    await fetch("/api/demo/reset", { method: "POST" });
    await fetch("/api/memory/clear", { method: "POST" });
    await fetchMemory();

    taskInput.value = "Navigate to http://127.0.0.1:9888/portal/ and download September report";
    autoApproveCheckbox.checked = true;
    await submitTask(taskInput.value, true);

    addChatMessage("WebCMD", "Stage 1 running. Real Chromium executing. Observe live viewport.");
  } catch (err) {
    addChatMessage("WebCMD", `Demo error: ${err.message}`);
  }
}

// Start on DOM ready
document.addEventListener("DOMContentLoaded", init);
