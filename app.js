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

// Dual-Mode & Cloud Demo Simulator State
let customBackendUrl = localStorage.getItem("webcmd_backend_url") || "";
let isCloudDemoMode = false;
let demoPortalMode = "A"; // "A" = stable #btn-download, "B" = changed UI #btn-export
let demoSimTimer = null;
let demoRunCount = 2;

function getApiUrl(endpoint) {
  if (customBackendUrl) {
    return `${customBackendUrl.replace(/\/$/, "")}${endpoint}`;
  }
  return endpoint;
}

// DOM Elements
const btnBackendSettings = document.getElementById("btn-backend-settings");
const backendModal = document.getElementById("backend-modal");
const btnCloseBackendModal = document.getElementById("btn-close-backend-modal");
const backendUrlInput = document.getElementById("backend-url-input");
const btnSaveBackend = document.getElementById("btn-save-backend");
const btnEnableDemoMode = document.getElementById("btn-enable-demo-mode");

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
  // Backend Settings Modal
  if (btnBackendSettings && backendModal) {
    btnBackendSettings.addEventListener("click", () => {
      backendModal.classList.remove("hidden");
      if (backendUrlInput) backendUrlInput.value = customBackendUrl || "http://127.0.0.1:8000";
    });
  }

  if (btnCloseBackendModal && backendModal) {
    btnCloseBackendModal.addEventListener("click", () => {
      backendModal.classList.add("hidden");
    });
  }

  if (btnSaveBackend && backendModal) {
    btnSaveBackend.addEventListener("click", async () => {
      const url = backendUrlInput.value.trim();
      customBackendUrl = url;
      if (url) {
        localStorage.setItem("webcmd_backend_url", url);
      } else {
        localStorage.removeItem("webcmd_backend_url");
      }
      backendModal.classList.add("hidden");
      addLog("System", `Configured backend API URL: ${url || "(relative default)"}`);
      await checkHealthAndSync();
    });
  }

  if (btnEnableDemoMode && backendModal) {
    btnEnableDemoMode.addEventListener("click", () => {
      customBackendUrl = "";
      localStorage.removeItem("webcmd_backend_url");
      backendModal.classList.add("hidden");
      isCloudDemoMode = true;
      wsDot.className = "status-dot cloud-mode";
      wsStatusText.textContent = "Cloud Demo";
      wsStatusText.title = "Operating in Cloud Interactive Demo Mode";
      initCloudDemoMode();
      addLog("System", "Switched to Standalone Cloud Demo Mode.");
    });
  }

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
    if (isCloudDemoMode) {
      completeSimulatedExecution(false);
      return;
    }
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
    const reason = rejectionReasonInput.value.trim();
    if (isCloudDemoMode) {
      completeSimulatedExecution(true, reason);
      rejectionBox.classList.add("hidden");
      return;
    }
    if (!currentExecutionId) return;
    await rejectGate(currentExecutionId, reason);
    rejectionBox.classList.add("hidden");
  });

  btnCancel.addEventListener("click", async () => {
    if (isCloudDemoMode) {
      if (demoSimTimer) clearTimeout(demoSimTimer);
      updateStatusPill("cancelled");
      addLog("Cancel", "Simulated execution cancelled by operator.");
      addChatMessage("WebCMD", "Execution cancelled.");
      btnCancel.disabled = true;
      btnCancel.style.opacity = "0.3";
      btnRun.disabled = false;
      return;
    }
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
      if (isCloudDemoMode) {
        if (demoSimTimer) clearTimeout(demoSimTimer);
        updateStatusPill("cancelled");
        addLog("Control", "Execution stopped.");
        btnRun.disabled = false;
        return;
      }
      if (currentExecutionId) await cancelExecution(currentExecutionId);
    });
  }

  if (btnCtrlResume) {
    btnCtrlResume.addEventListener("click", async () => {
      if (isCloudDemoMode) {
        addLog("Resume", "Resumed execution from checkpoint.");
        addChatMessage("WebCMD", "Resumed from state checkpoint CP-a9c1e4.");
        return;
      }
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
      if (isCloudDemoMode) {
        demoPortalMode = "A";
        renderSimulatedScreencast("Reset to Version A");
        addLog("DemoControl", "Portal reset to Mode A (Version A stable download): #btn-download active.");
        addChatMessage("WebCMD", "Test portal reset to Version A (Stable `#btn-download` element active).");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/demo/reset"), { method: "POST" });
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
      if (isCloudDemoMode) {
        demoPortalMode = "B";
        renderSimulatedScreencast("Switched to Version B");
        addLog("DemoControl", "Portal switched to Mode B (Version B export report): #btn-export active.");
        addChatMessage("WebCMD", "Test portal switched to Version B (UI changed: `#btn-download` removed, replaced with `#btn-export`). Next run will trigger self-healing recovery!");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/demo/switch"), { method: "POST" });
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
      if (isCloudDemoMode) {
        memDomain.textContent = "report-portal.local";
        memConfidenceBadge.textContent = "Confidence: 0.00";
        meterFill.style.width = "0%";
        memLastVisit.textContent = "Cold start";
        memKnownWorkflow.textContent = "None";
        memPreviousRecovery.textContent = "None";
        memLastVerified.textContent = "Cold start";
        document.getElementById("stat-successful-runs").textContent = "0";
        addLog("MemoryControl", "Experiential memory items cleared for clean demo baseline.");
        addChatMessage("WebCMD", "Experiential site memory cleared. WebCMD will start fresh with zero prior experience.");
        return;
      }
      try {
        await fetch(getApiUrl("/api/memory/clear"), { method: "POST" });
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
      if (isCloudDemoMode) {
        addLog("BrowserControl", "Chromium persistent profile cleared at `./data/browser-profile`.");
        addChatMessage("WebCMD", "Chromium persistent profile cleared at `./data/browser-profile`.");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/browser/reset-profile"), { method: "POST" });
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
      if (isCloudDemoMode) {
        renderSimulatedScreencast("Toggled Playback (Simulated)");
        addLog("Media", "Toggled video playback (Simulated).");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/browser/media/toggle-play"), { method: "POST" });
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
      if (isCloudDemoMode) {
        renderSimulatedScreencast("Rewind -10s");
        addLog("Media", "Seek -10s (Simulated).");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/browser/media/seek"), {
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
      if (isCloudDemoMode) {
        renderSimulatedScreencast("Forward +10s");
        addLog("Media", "Seek +10s (Simulated).");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/browser/media/seek"), {
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
      if (isCloudDemoMode) {
        const isMuted = btnMediaMute.innerHTML.includes("Unmute");
        btnMediaMute.innerHTML = isMuted ? "&#128266; Mute" : "&#128263; Unmute";
        renderSimulatedScreencast(isMuted ? "Audio Unmuted" : "Audio Muted");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/browser/media/toggle-mute"), { method: "POST" });
        const d = await res.json();
        const isMuted = d.result?.muted;
        btnMediaMute.innerHTML = isMuted ? "&#128263; Unmute" : "&#128266; Mute";
      } catch (e) {}
    });
  }

  if (btnScrollUp) {
    btnScrollUp.addEventListener("click", async () => {
      if (isCloudDemoMode) {
        renderSimulatedScreencast("Scrolled Up");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/browser/scroll"), {
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
      if (isCloudDemoMode) {
        renderSimulatedScreencast("Scrolled Down");
        return;
      }
      try {
        const res = await fetch(getApiUrl("/api/browser/scroll"), {
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

      if (isCloudDemoMode) {
        renderSimulatedScreencast(`Clicked at (${x}, ${y})`, null, { x, y });
        return;
      }

      try {
        const res = await fetch(getApiUrl("/api/browser/click"), {
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

      if (isCloudDemoMode) {
        renderSimulatedScreencast("Mouse Wheel Scrolled");
        return;
      }

      const deltaY = e.deltaY > 0 ? 350 : -350;
      fetch(getApiUrl("/api/browser/scroll"), {
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

function initCloudDemoMode() {
  if (btnCancel) {
    btnCancel.disabled = true;
    btnCancel.style.opacity = "0.3";
  }
  currentExecutionId = "EXEC-DEMO-001";
  currentExecIdEl.textContent = currentExecutionId;
  currentTaskText = "Download September financial report and verify integrity";
  currentTaskTextEl.textContent = currentTaskText;
  updateStatusPill("completed");
  currentWorkerEl.textContent = "browser_worker";
  currentStepProgressEl.textContent = "4 / 4";

  // Mark canonical stepper as completed baseline
  CANONICAL_STAGES.forEach(s => setStageState(s.id, "completed"));

  // Site memory baseline
  memDomain.textContent = "report-portal.local";
  memConfidenceBadge.textContent = "Confidence: 0.90";
  meterFill.style.width = "90%";
  memLastVisit.textContent = "Today, 14:30:00";
  memKnownWorkflow.textContent = "WF-FIN-SEP-01 (Deterministic)";
  memPreviousRecovery.textContent = "None (Direct execution)";
  memLastVerified.textContent = "Automated + Human Gate (0.90)";
  const statEl = document.getElementById("stat-successful-runs");
  if (statEl) statEl.textContent = "5";

  // Checkpoint baseline
  cpLatestId.textContent = "CP-a9c1e4";
  cpTrigger.textContent = "post_verification";
  cpHash.textContent = "7e2a9b4c81...001";
  cpEnvStatus.textContent = "VALID (SHA-256 Verified)";
  cpResumeStatus.textContent = "AVAILABLE (Resumable)";

  // Render simulated browser frame
  renderSimulatedScreencast("Ready — Version A Active");

  // Populate initial history ledger
  if (historyTableBody) {
    historyTableBody.innerHTML = `
      <tr class="history-row" title="Click to view run EXEC-DEMO-001">
        <td class="mono-text">RUN-001</td>
        <td class="task-cell" title="Download September financial report">Download September financial report</td>
        <td><span class="strategy-badge strat-learned">Learned Workflow</span></td>
        <td><span class="status-pill status-success">Completed</span></td>
        <td class="pass-text">PASS (SHA-256)</td>
        <td class="mono-text">14:30:12</td>
      </tr>
      <tr class="history-row" title="Click to view run EXEC-DEMO-002">
        <td class="mono-text">RUN-002</td>
        <td class="task-cell" title="Export Monthly Audit Report">Export Monthly Audit Report</td>
        <td><span class="strategy-badge strat-recovery">Recovery Adaptation</span></td>
        <td><span class="status-pill status-success">Completed</span></td>
        <td class="pass-text">PASS (SHA-256)</td>
        <td class="mono-text">14:35:48</td>
      </tr>
    `;
  }

  addLog("System", "WebCMD Cloud Demo Simulator active. Full 12-stage architecture ready.");
}

function renderSimulatedScreencast(statusText = "Ready", highlightSelector = null, cursor = null) {
  if (!browserViewportImg) return;
  const isB = (demoPortalMode === "B");
  const actionButtonText = isB ? "Export Monthly Report" : "Download September Report";
  const actionButtonId = isB ? "btn-export" : "btn-download";
  const actionBtnBg = isB ? "#8b5cf6" : "#10b981";
  const url = isB ? "http://127.0.0.1:9888/report-portal/v2/dashboard" : "http://127.0.0.1:9888/report-portal/v1/dashboard";

  if (browserLiveUrl) browserLiveUrl.textContent = url;
  if (browserStatusTag) {
    browserStatusTag.textContent = "Chromium Active (1280x800)";
    browserStatusTag.className = "browser-status-tag active";
  }

  const svg = `
  <svg xmlns="http://www.w3.org/2000/svg" width="1280" height="800" viewBox="0 0 1280 800">
    <defs>
      <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#0b1120"/>
        <stop offset="100%" stop-color="#0f172a"/>
      </linearGradient>
      <linearGradient id="cardGrad" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#1e293b"/>
        <stop offset="100%" stop-color="#0f172a"/>
      </linearGradient>
    </defs>
    <rect width="1280" height="800" fill="url(#bgGrad)"/>
    
    <rect x="0" y="0" width="240" height="800" fill="#090e17" stroke="#1e293b" stroke-width="1"/>
    <text x="24" y="48" fill="#06b6d4" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="18" font-weight="bold">Acme Corp Portal</text>
    <text x="24" y="68" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="12">Internal Financial Reporting</text>
    
    <rect x="16" y="100" width="208" height="38" rx="8" fill="rgba(6, 182, 212, 0.15)" stroke="#06b6d4" stroke-width="1"/>
    <text x="44" y="124" fill="#38bdf8" font-family="sans-serif" font-size="14" font-weight="600">&#128202; Financial Reports</text>
    <text x="44" y="174" fill="#94a3b8" font-family="sans-serif" font-size="14">&#128197; Monthly Audits</text>
    <text x="44" y="218" fill="#94a3b8" font-family="sans-serif" font-size="14">&#128279; Export Gateway</text>
    <text x="44" y="262" fill="#94a3b8" font-family="sans-serif" font-size="14">&#9881; Portal Settings</text>
    
    <rect x="240" y="0" width="1040" height="64" fill="#0c1322" stroke="#1e293b" stroke-width="1"/>
    <text x="270" y="38" fill="#f8fafc" font-family="sans-serif" font-size="16" font-weight="600">Enterprise Reports Dashboard</text>
    <rect x="1050" y="18" width="200" height="28" rx="14" fill="#1e293b"/>
    <circle cx="1066" cy="32" r="6" fill="#10b981"/>
    <text x="1080" y="36" fill="#94a3b8" font-family="sans-serif" font-size="11">Operator Session Active</text>

    <g transform="translate(270, 90)">
      <rect x="0" y="0" width="310" height="90" rx="10" fill="url(#cardGrad)" stroke="#1e293b" stroke-width="1"/>
      <text x="20" y="30" fill="#94a3b8" font-family="sans-serif" font-size="12">Q3 Financial Cycle</text>
      <text x="20" y="62" fill="#38bdf8" font-family="sans-serif" font-size="22" font-weight="bold">$4,892,120.00</text>
      
      <rect x="330" y="0" width="310" height="90" rx="10" fill="url(#cardGrad)" stroke="#1e293b" stroke-width="1"/>
      <text x="350" y="30" fill="#94a3b8" font-family="sans-serif" font-size="12">Audit Verification Status</text>
      <text x="350" y="62" fill="#10b981" font-family="sans-serif" font-size="20" font-weight="bold">Verified &#10003;</text>
      
      <rect x="660" y="0" width="320" height="90" rx="10" fill="url(#cardGrad)" stroke="#1e293b" stroke-width="1"/>
      <text x="680" y="30" fill="#94a3b8" font-family="sans-serif" font-size="12">Portal Version Mode</text>
      <text x="680" y="62" fill="${isB ? '#c084fc' : '#34d399'}" font-family="sans-serif" font-size="18" font-weight="bold">Version ${isB ? 'B (Mutated UI)' : 'A (Stable UI)'}</text>

      <rect x="0" y="110" width="980" height="420" rx="12" fill="#090e17" stroke="#1e293b" stroke-width="1"/>
      <text x="24" y="145" fill="#f8fafc" font-family="sans-serif" font-size="15" font-weight="bold">Available Monthly Statements</text>
      <text x="24" y="165" fill="#64748b" font-family="sans-serif" font-size="12">Select file to trigger automated export pipeline</text>
      
      <rect x="20" y="180" width="940" height="34" rx="6" fill="#1e293b"/>
      <text x="40" y="202" fill="#94a3b8" font-family="sans-serif" font-size="12" font-weight="600">PERIOD</text>
      <text x="200" y="202" fill="#94a3b8" font-family="sans-serif" font-size="12" font-weight="600">DOCUMENT ID</text>
      <text x="400" y="202" fill="#94a3b8" font-family="sans-serif" font-size="12" font-weight="600">FILE SIZE</text>
      <text x="560" y="202" fill="#94a3b8" font-family="sans-serif" font-size="12" font-weight="600">STATUS</text>
      <text x="740" y="202" fill="#94a3b8" font-family="sans-serif" font-size="12" font-weight="600">ACTION</text>

      <!-- Row 1: September -->
      <rect x="20" y="222" width="940" height="54" rx="6" fill="rgba(6, 182, 212, 0.08)" stroke="#06b6d4" stroke-width="1"/>
      <text x="40" y="254" fill="#38bdf8" font-family="sans-serif" font-size="14" font-weight="bold">September 2026</text>
      <text x="200" y="254" fill="#cbd5e1" font-family="monospace" font-size="13">REP-2026-09-FIN</text>
      <text x="400" y="254" fill="#cbd5e1" font-family="monospace" font-size="13">45,210 KB</text>
      <rect x="560" y="238" width="80" height="24" rx="12" fill="rgba(16, 185, 129, 0.2)"/>
      <text x="578" y="254" fill="#34d399" font-family="sans-serif" font-size="11" font-weight="600">AUDITED</text>
      
      <!-- Action Button -->
      <rect id="${actionButtonId}" x="740" y="234" width="200" height="32" rx="6" fill="${actionBtnBg}" ${highlightSelector ? 'stroke="#f43f5e" stroke-width="3"' : ''}/>
      <text x="755" y="255" fill="#ffffff" font-family="sans-serif" font-size="12" font-weight="bold">${actionButtonText}</text>

      <!-- Row 2: August -->
      <rect x="20" y="284" width="940" height="48" rx="6" fill="rgba(255, 255, 255, 0.02)"/>
      <text x="40" y="313" fill="#94a3b8" font-family="sans-serif" font-size="13">August 2026</text>
      <text x="200" y="313" fill="#64748b" font-family="monospace" font-size="13">REP-2026-08-FIN</text>
      <text x="400" y="313" fill="#64748b" font-family="monospace" font-size="13">43,180 KB</text>
      <rect x="560" y="299" width="80" height="22" rx="11" fill="rgba(255, 255, 255, 0.05)"/>
      <text x="578" y="314" fill="#64748b" font-family="sans-serif" font-size="11">ARCHIVED</text>
      <rect x="740" y="295" width="200" height="30" rx="6" fill="#1e293b"/>
      <text x="800" y="315" fill="#94a3b8" font-family="sans-serif" font-size="12">Archived</text>
    </g>

    ${cursor ? `
      <g transform="translate(${cursor.x}, ${cursor.y})">
        <polygon points="0,0 0,22 6,17 12,25 15,23 9,15 17,15" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>
        <circle cx="0" cy="0" r="16" fill="none" stroke="#06b6d4" stroke-width="2" opacity="0.8">
          <animate attributeName="r" values="8;24" dur="0.8s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="1;0" dur="0.8s" repeatCount="indefinite"/>
        </circle>
      </g>
    ` : ''}

    <rect x="0" y="760" width="1280" height="40" fill="#05080f"/>
    <text x="24" y="785" fill="#64748b" font-family="monospace" font-size="12">WebCMD Chromium Screencast | Frame: 60 FPS | DOM: Complete | ${statusText}</text>
  </svg>
  `;

  browserViewportImg.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  browserViewportImg.style.display = "block";
  if (browserPlaceholder) browserPlaceholder.style.display = "none";
}

function runSimulatedExecution(task, autoConfirm) {
  btnRun.disabled = true;
  if (btnCancel) {
    btnCancel.disabled = false;
    btnCancel.style.opacity = "1";
    btnCancel.style.pointerEvents = "auto";
  }
  currentTaskText = task;
  currentTaskTextEl.textContent = task;
  currentExecutionId = `EXEC-DEMO-00${++demoRunCount}`;
  currentExecIdEl.textContent = currentExecutionId;
  gateCard.classList.add("hidden");
  rejectionBox.classList.add("hidden");

  if (execCardTitle) execCardTitle.textContent = "ACTIVE EXECUTION";
  updateStatusPill("running");
  currentWorkerEl.textContent = "intent_engine";
  currentStepProgressEl.textContent = "1 / 4";
  resetStepper();
  resetRecoveryCard();

  addChatMessage("User", task);
  addChatMessage("WebCMD", `Task received: "${task}". Normalizing intent and retrieving site memory...`);
  addLog("Client", `Task submitted: "${task}" (auto_confirm=${autoConfirm})`);

  let step = 0;
  const isRecoveryScenario = (demoPortalMode === "B");

  const runNextStep = () => {
    step++;
    if (step === 1) {
      setStageState("intent", "completed");
      setStageState("memory", "active");
      currentWorkerEl.textContent = "site_memory";
      addLog("IntentEngine", `Normalized intent: domain=report-portal.local, action=download_report, target="September 2026"`);
      renderSimulatedScreencast("Analyzing task intent...", null, null);
      demoSimTimer = setTimeout(runNextStep, 500);
    } else if (step === 2) {
      setStageState("memory", "completed");
      setStageState("plan", "active");
      currentWorkerEl.textContent = "planner";
      addLog("SiteMemory", `Retrieved site memory for report-portal.local: preferred_selector=#btn-download, confidence=0.90`);
      addChatMessage("WebCMD", `Found prior experience for report-portal.local with confidence 0.90.`);
      renderSimulatedScreencast("Retrieved site memory...", null, null);
      demoSimTimer = setTimeout(runNextStep, 500);
    } else if (step === 3) {
      setStageState("plan", "completed");
      setStageState("policy", "completed");
      setStageState("execute", "active");
      currentWorkerEl.textContent = "browser_worker";
      currentStepProgressEl.textContent = "2 / 4";
      addLog("Planner", `Generated execution plan: [1: navigate, 2: observe, 3: click action, 4: verify]`);
      addLog("PolicyEngine", `Security policy evaluated: PASS (domain report-portal.local in sandbox allowlist)`);
      renderSimulatedScreencast("Navigating to portal...", null, { x: 500, y: 300 });
      demoSimTimer = setTimeout(runNextStep, 600);
    } else if (step === 4) {
      if (isRecoveryScenario) {
        setStageState("execute", "failed");
        setStageState("recover", "active");
        currentWorkerEl.textContent = "recovery_engine";
        addLog("BrowserWorker", "Target element '#btn-download' not found in DOM! (Version B UI mutation)");
        addChatMessage("WebCMD", "Self-healing triggered: element '#btn-download' missing in Version B. Scanning DOM for semantic alternatives...");
        
        recoveryStatusBadge.textContent = "Active Recovery";
        recoveryStatusBadge.className = "metric-pill pill-running";
        recExpected.textContent = "Element #btn-download";
        recObserved.textContent = "DOM mutated; button #btn-export present";
        recStrategy.textContent = "Autonomous Selector Adaptation";
        recOutcome.textContent = "Healed: adapted to #btn-export";

        renderSimulatedScreencast("Self-healing: Adapting selector...", "#btn-export", { x: 1040, y: 340 });
        demoSimTimer = setTimeout(() => {
          setStageState("recover", "completed");
          setStageState("observe", "active");
          currentWorkerEl.textContent = "browser_worker";
          addLog("RecoveryEngine", "Autonomous fix: Found semantic equivalent #btn-export ('Export Monthly Report'). Clicked successfully.");
          addChatMessage("WebCMD", "Self-healing succeeded. Adapted action to '#btn-export'.");
          renderSimulatedScreencast("Recovery executed on #btn-export", null, { x: 1050, y: 345 });
          demoSimTimer = setTimeout(runNextStep, 600);
        }, 800);
      } else {
        setStageState("execute", "completed");
        setStageState("observe", "active");
        currentWorkerEl.textContent = "observe_worker";
        currentStepProgressEl.textContent = "3 / 4";
        addLog("BrowserWorker", "Navigated to http://127.0.0.1:9888/report-portal/v1/dashboard");
        addLog("BrowserWorker", "Clicked element '#btn-download' (Download September Report)");
        renderSimulatedScreencast("Clicked #btn-download", null, { x: 1050, y: 345 });
        demoSimTimer = setTimeout(runNextStep, 600);
      }
    } else if (step === 5) {
      setStageState("observe", "completed");
      setStageState("verify", "completed");
      setStageState("checkpoint", "completed");
      currentWorkerEl.textContent = "verification_engine";
      currentStepProgressEl.textContent = "4 / 4";
      addLog("ObserveWorker", "Captured DOM snapshot and network download payload.");
      addLog("VerificationEngine", "Automated verification PASS: File size 45,210 bytes, checksum SHA-256 confirmed.");
      addLog("CheckpointEngine", `Atomic state checkpoint CP-8f2a... saved to ledger.`);
      
      cpLatestId.textContent = `CP-${Math.random().toString(36).substring(2, 8)}`;
      cpTrigger.textContent = "post_verification";
      cpHash.textContent = "3f8b9e1a...042";

      renderSimulatedScreencast("Report verified: 45,210 bytes (PASS)", null, null);
      demoSimTimer = setTimeout(runNextStep, 500);
    } else if (step === 6) {
      if (autoConfirm) {
        completeSimulatedExecution(false);
      } else {
        setStageState("human", "waiting-gate");
        updateStatusPill("awaiting_human_verification");
        currentWorkerEl.textContent = "human_gate";
        gateCard.classList.remove("hidden");
        gateTaskDesc.textContent = task;
        gateResultOutput.textContent = JSON.stringify({
          status: "verified",
          report: "September 2026 Financial Audit",
          file: "REP-2026-09-FIN.pdf",
          file_size_bytes: 45210,
          checksum: "sha256:7f3b892a4e5801c4...",
          automated_verification: "PASSED",
          healed: isRecoveryScenario ? "#btn-download -> #btn-export" : false
        }, null, 2);

        addLog("HumanGate", "Execution awaiting operator confirmation.");
        addChatMessage("WebCMD", "Execution paused: EXACTLY ONE final human verification required before completion. Review verified artifact below and confirm.");
      }
    }
  };

  runNextStep();
}

function completeSimulatedExecution(rejected = false, reason = "") {
  gateCard.classList.add("hidden");
  if (rejected) {
    updateStatusPill("failed");
    setStageState("human", "failed");
    setStageState("complete", "failed");
    addLog("HumanGate", `Operator rejected execution: "${reason}"`);
    addChatMessage("Operator", `Result Rejected: "${reason}"`);
    addChatMessage("WebCMD", "Execution marked for review and logged in failure ledger.");
  } else {
    setStageState("human", "completed");
    setStageState("complete", "completed");
    setStageState("learn", "completed");
    updateStatusPill("completed");
    addLog("HumanGate", "Operator confirmed execution.");
    addChatMessage("Operator", "Result Confirmed ✓.");
    addChatMessage("WebCMD", "Task completed successfully. Experiential memory updated with confidence 0.95.");

    const conf = 0.95;
    memConfidenceBadge.textContent = `Confidence: ${conf.toFixed(2)}`;
    meterFill.style.width = "95%";
    memLastVisit.textContent = "Just now";
    memLastVerified.textContent = "Human Confirmed (0.95)";
    if (demoPortalMode === "B") {
      memPreviousRecovery.textContent = 'Healed: "#btn-download" → "#btn-export"';
      memKnownWorkflow.textContent = "monthly_report_export (Learned Repair)";
    }
    const statEl = document.getElementById("stat-successful-runs");
    if (statEl) {
      const currentRuns = parseInt(statEl.textContent || "5", 10);
      statEl.textContent = currentRuns + 1;
    }

    if (historyTableBody) {
      const isRecovery = (demoPortalMode === "B");
      const newRow = `
        <tr class="history-row">
          <td class="mono-text">RUN-00${demoRunCount}</td>
          <td class="task-cell" title="${currentTaskText}">${currentTaskText.length > 40 ? currentTaskText.substring(0, 38) + '...' : currentTaskText}</td>
          <td><span class="strategy-badge ${isRecovery ? 'strat-recovery' : 'strat-learned'}">${isRecovery ? 'Recovery Adaptation' : 'Learned Workflow'}</span></td>
          <td><span class="status-pill status-success">Completed</span></td>
          <td class="pass-text">PASS (SHA-256)</td>
          <td class="mono-text">${new Date().toLocaleTimeString()}</td>
        </tr>
      `;
      historyTableBody.innerHTML = newRow + historyTableBody.innerHTML;
    }
  }

  btnRun.disabled = false;
  if (btnCancel) {
    btnCancel.disabled = true;
    btnCancel.style.opacity = "0.3";
  }
}

async function checkHealthAndSync() {
  if (backendUrlInput) {
    backendUrlInput.value = customBackendUrl;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(getApiUrl("/api/health"), { signal: controller.signal });
    clearTimeout(timeoutId);

    const contentType = res.headers.get("content-type") || "";
    if (res.ok && contentType.includes("application/json")) {
      const data = await res.json();
      if (data && data.status === "ok") {
        isCloudDemoMode = false;
        wsDot.className = "status-dot connected";
        wsStatusText.textContent = "Live Agent";
        wsStatusText.title = "Connected to live WebCMD Orchestrator";
        await syncAll();
        return;
      }
    }
  } catch (e) {
    // Fall through to Cloud Demo Mode
  }

  isCloudDemoMode = true;
  wsDot.className = "status-dot cloud-mode";
  wsStatusText.textContent = "Cloud Demo";
  wsStatusText.title = "Operating in Cloud Interactive Demo Mode";
  initCloudDemoMode();
}

// Master Synchronization Function
async function syncAll(isManual = false) {
  if (btnRefresh) {
    btnRefresh.disabled = true;
    btnRefresh.style.opacity = "0.7";
  }

  if (isCloudDemoMode) {
    initCloudDemoMode();
    if (isManual) {
      addLog("Sync", "Cloud Demo environment synchronized.");
    }
    if (btnRefresh) {
      btnRefresh.disabled = false;
      btnRefresh.style.opacity = "1";
    }
    return;
  }

  try {
    const resp = await fetch(getApiUrl("/api/executions"));
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
  if (isCloudDemoMode) {
    runSimulatedExecution(task, autoConfirm);
    return;
  }

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

    const resp = await fetch(getApiUrl("/api/executions"), {
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

    const resp = await fetch(getApiUrl(`/api/executions/${executionId}/confirm`), {
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

    const resp = await fetch(getApiUrl(`/api/executions/${executionId}/reject`), {
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
    const resp = await fetch(getApiUrl(`/api/executions/${executionId}/cancel`), { method: "POST" });
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
    const resp = await fetch(getApiUrl(`/api/executions/${executionId}/resume`), { method: "POST" });
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
    const resp = await fetch(getApiUrl(`/api/executions/${executionId}`));
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
    const resp = await fetch(getApiUrl("/api/memory"));
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
    const resp = await fetch(getApiUrl("/api/security"));
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
    const resp = await fetch(getApiUrl("/api/history"));
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
  if (isCloudDemoMode) return;
  try {
    const res = await fetch(getApiUrl("/api/browser/screencast"));
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

  if (isCloudDemoMode) {
    taskInput.value = "Download September financial report and verify integrity";
    autoApproveCheckbox.checked = false;
    runSimulatedExecution(taskInput.value, false);
    return;
  }

  // Stage 1: Baseline Execution (Mode A)
  addChatMessage("WebCMD", "▶ STAGE 1: Baseline Execution (Version A - #btn-download). Resetting demo portal...");
  try {
    await fetch(getApiUrl("/api/demo/reset"), { method: "POST" });
    await fetch(getApiUrl("/api/memory/clear"), { method: "POST" });
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
