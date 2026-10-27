/**
 * AWS EKS Web CLI - Client Application
 * Provides browser-based terminal access for inspecting resources across any namespace.
 * Enforces security guardrails to strictly block deletion commands and shell injection.
 */

const API_BASE = "";

// State
let authToken = localStorage.getItem("eks_token") || null;
let currentUser = { username: "developer", allowed_namespaces: ["*"], default_namespace: "ns-4" };
let activeNamespace = "ns-4";
let commandHistory = [];
let historyIndex = -1;

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await ensureAuthentication();
  await loadNamespaces();
  printWelcomeBanner();
});

// Setup UI Event Listeners
function setupEventListeners() {
  const cliInput = document.getElementById("cli-input");
  const runBtn = document.getElementById("btn-run-cmd");
  const clearBtn = document.getElementById("btn-clear-term");
  const nsSelect = document.getElementById("ns-select");
  const auditBtn = document.getElementById("btn-audit-drawer");
  const closeAuditBtn = document.getElementById("btn-close-audit");
  const drawerOverlay = document.getElementById("drawer-overlay");

  // Enter key in input
  cliInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      executeCurrentInput();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      navigateHistory(-1);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      navigateHistory(1);
    } else if (e.ctrlKey && e.key === "l") {
      e.preventDefault();
      clearTerminal();
    }
  });

  runBtn.addEventListener("click", executeCurrentInput);
  clearBtn.addEventListener("click", clearTerminal);

  // Namespace dropdown change
  nsSelect.addEventListener("change", (e) => {
    activeNamespace = e.target.value;
    updateTerminalPrompt();
    loadVisualizerServices();
  });

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const tabName = btn.dataset.tab;
      if (tabName === "terminal") {
        document.getElementById("terminal-view").style.display = "flex";
        document.getElementById("visualizer-view").classList.remove("active");
      } else {
        document.getElementById("terminal-view").style.display = "none";
        document.getElementById("visualizer-view").classList.add("active");
        loadVisualizerServices();
      }
    });
  });

  // Quick action chips
  document.querySelectorAll(".quick-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const cmd = chip.dataset.cmd;
      cliInput.value = cmd;
      executeCurrentInput();
    });
  });

  // Audit Drawer
  auditBtn.addEventListener("click", openAuditDrawer);
  closeAuditBtn.addEventListener("click", closeAuditDrawer);
  drawerOverlay.addEventListener("click", closeAuditDrawer);
}

// Authentication
async function ensureAuthentication() {
  if (!authToken) {
    await loginUser("developer");
  } else {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        currentUser = await res.json();
        updateUserUI();
      } else {
        await loginUser("developer");
      }
    } catch {
      await loginUser("developer");
    }
  }
}

async function loginUser(username) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username || "developer" }),
    });
    if (!res.ok) throw new Error("Authentication failed");
    const data = await res.json();
    authToken = data.access_token;
    currentUser = data.user;
    localStorage.setItem("eks_token", authToken);
    activeNamespace = currentUser.default_namespace || "ns-4";
    updateUserUI();
  } catch (err) {
    console.error("Login error:", err);
  }
}

// Load cluster namespaces into dropdown
async function loadNamespaces() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/namespaces`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    if (res.ok) {
      const data = await res.json();
      const nsSelect = document.getElementById("ns-select");
      const list = data.allowed_namespaces || ["ns-4", "default", "kube-system"];
      nsSelect.innerHTML = list
        .map(
          (ns) =>
            `<option value="${ns}" ${ns === activeNamespace ? "selected" : ""}>${ns}</option>`
        )
        .join("");
    }
  } catch (err) {
    console.warn("Could not fetch namespaces list:", err);
  }
}

// Update UI
function updateUserUI() {
  if (!currentUser) return;

  const userNameEl = document.getElementById("user-name");
  const userAvatarEl = document.getElementById("user-avatar");
  if (userNameEl) userNameEl.textContent = currentUser.username;
  if (userAvatarEl) userAvatarEl.textContent = currentUser.username.charAt(0).toUpperCase();

  updateTerminalPrompt();
}

function updateTerminalPrompt() {
  const promptUser = document.getElementById("prompt-user");
  const promptNs = document.getElementById("prompt-ns");
  const clusterPill = document.getElementById("cluster-ns-pill");
  const bannerNs = document.getElementById("banner-ns");
  const bannerNsChip = document.getElementById("banner-ns-chip");

  if (promptUser && currentUser) promptUser.textContent = currentUser.username;
  if (promptNs) promptNs.textContent = activeNamespace;
  if (clusterPill) clusterPill.textContent = activeNamespace;
  if (bannerNs) bannerNs.textContent = activeNamespace;
  if (bannerNsChip) bannerNsChip.textContent = activeNamespace;
}

// Command Execution
async function executeCurrentInput() {
  const inputEl = document.getElementById("cli-input");
  const rawCmd = inputEl.value.trim();
  if (!rawCmd) return;

  // Record into history
  commandHistory.push(rawCmd);
  historyIndex = commandHistory.length;
  inputEl.value = "";

  // Append command entry to terminal body
  appendCommandToTerminal(rawCmd);

  // Send to backend
  try {
    const res = await fetch(`${API_BASE}/api/v1/cli/exec`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        command: rawCmd,
        namespace: activeNamespace,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      appendOutputToTerminal(data.detail || "Request failed", true, 0, false);
    } else if (data.exit_code !== 0) {
      const errText = data.error || data.output || "Command failed";
      appendOutputToTerminal(errText, true, data.duration_ms, data.is_mock);
    } else {
      appendOutputToTerminal(data.output, false, data.duration_ms, data.is_mock);
    }
  } catch (err) {
    appendOutputToTerminal(`Network error: ${err.message}`, true, 0, false);
  }

  scrollTerminalToBottom();
}

function appendCommandToTerminal(cmd) {
  const termBody = document.getElementById("terminal-body");
  const entry = document.createElement("div");
  entry.className = "term-entry";
  entry.innerHTML = `
    <div class="term-cmd-line">
      <span class="term-prompt">user@eks</span>
      <span class="term-ns-tag">[${activeNamespace}]</span>
      <span class="term-cmd-text">$ ${escapeHtml(cmd)}</span>
      <span class="term-meta">${new Date().toLocaleTimeString()}</span>
    </div>
    <div class="term-output-placeholder"></div>
  `;
  termBody.appendChild(entry);
}

function appendOutputToTerminal(output, isError, durationMs, isMock) {
  const termBody = document.getElementById("terminal-body");
  const lastEntry = termBody.lastElementChild;
  if (!lastEntry) return;

  const placeholder = lastEntry.querySelector(".term-output-placeholder");
  if (!placeholder) return;

  const outputDiv = document.createElement("div");
  outputDiv.className = `term-output ${isError ? "error" : ""}`;

  let contentHtml = "";
  if (isMock) {
    contentHtml += `<div class="mock-indicator">Cluster Simulation Mode (${durationMs.toFixed(1)}ms)</div>\n`;
  } else if (!isError && durationMs > 0) {
    contentHtml += `<div style="font-size:10px; color:#64748b; margin-bottom:4px;">Executed in ${durationMs.toFixed(1)}ms</div>`;
  }

  contentHtml += highlightKubectlOutput(output);
  outputDiv.innerHTML = contentHtml;
  placeholder.replaceWith(outputDiv);
}

function printWelcomeBanner() {
  const termBody = document.getElementById("terminal-body");
  const welcomeDiv = document.createElement("div");
  welcomeDiv.className = "term-entry";
  welcomeDiv.innerHTML = `
    <div class="term-output" style="color: #94a3b8; border-left: 2px solid #38bdf8; padding-left: 12px;">
<span style="color:#38bdf8; font-weight:700;">☸ AWS EKS Diagnostic Web CLI</span>
Access Scope: <span style="color:#10b981; font-weight:600;">All Namespaces Allowed</span>
Security Guardrail: <span style="color:#ef4444; font-weight:600;">Resource Deletions (kubectl delete) Strictly Blocked</span>

Quick Examples:
  • <span style="color:#38bdf8;">kubectl get services</span>
  • <span style="color:#38bdf8;">kubectl get pods -A</span>
  • <span style="color:#38bdf8;">kubectl get pods -n application-1</span>
  • <span style="color:#38bdf8;">kubectl describe service order-service</span>
  • <span style="color:#38bdf8;">kubectl logs &lt;pod-name&gt;</span>
    </div>
  `;
  termBody.appendChild(welcomeDiv);
}

function clearTerminal() {
  document.getElementById("terminal-body").innerHTML = "";
  printWelcomeBanner();
}

function scrollTerminalToBottom() {
  const termBody = document.getElementById("terminal-body");
  termBody.scrollTop = termBody.scrollHeight;
}

function navigateHistory(direction) {
  if (commandHistory.length === 0) return;
  historyIndex += direction;
  if (historyIndex < 0) historyIndex = 0;
  if (historyIndex >= commandHistory.length) {
    historyIndex = commandHistory.length;
    document.getElementById("cli-input").value = "";
    return;
  }
  document.getElementById("cli-input").value = commandHistory[historyIndex];
}

// Visualizer: Loads services in current namespace as cards
async function loadVisualizerServices() {
  const container = document.getElementById("visualizer-container");
  if (!container) return;

  container.innerHTML = `<div style="color:#94a3b8; font-size:13px; font-family:var(--font-mono); grid-column:1/-1;">Loading services for [${activeNamespace}]...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/v1/cli/exec`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        command: "kubectl get services",
        namespace: activeNamespace,
      }),
    });

    const data = await res.json();
    if (!res.ok || data.exit_code !== 0) {
      container.innerHTML = `<div style="color:#ef4444; font-size:13px; font-family:var(--font-mono); grid-column:1/-1;">No services found or unable to query [${activeNamespace}].</div>`;
      return;
    }

    const lines = data.output.trim().split("\n");
    if (lines.length <= 1) {
      container.innerHTML = `<div style="color:#94a3b8; font-size:13px; font-family:var(--font-mono); grid-column:1/-1;">No services found in namespace [${activeNamespace}].</div>`;
      return;
    }

    const cardsHtml = lines
      .slice(1)
      .map((line) => {
        const parts = line.trim().split(/\s+/);
        if (parts.length < 5) return "";
        const [name, type, clusterIp, externalIp, ports, age] = parts;
        return `
          <div class="service-card">
            <div class="card-header">
              <span class="svc-title">⚙ ${escapeHtml(name)}</span>
              <span class="svc-type-badge">${escapeHtml(type)}</span>
            </div>
            <div class="card-meta">
              <div><strong style="color:#94a3b8;">Cluster IP:</strong> ${escapeHtml(clusterIp)}</div>
              <div><strong style="color:#94a3b8;">Port(s):</strong> ${escapeHtml(ports || "N/A")}</div>
              <div><strong style="color:#94a3b8;">Age:</strong> ${escapeHtml(age || "N/A")}</div>
            </div>
            <div class="card-actions">
              <button class="btn-card" onclick="runQuickCommand('kubectl describe service ${name}')">Describe</button>
              <button class="btn-card" onclick="runQuickCommand('kubectl get endpoints ${name}')">Endpoints</button>
            </div>
          </div>
        `;
      })
      .join("");

    container.innerHTML = cardsHtml;
  } catch (err) {
    container.innerHTML = `<div style="color:#ef4444; font-size:12px;">Error: ${err.message}</div>`;
  }
}

window.runQuickCommand = function (cmd) {
  document.querySelector('.tab-btn[data-tab="terminal"]').click();
  document.getElementById("cli-input").value = cmd;
  executeCurrentInput();
};

// Real-time Audit Drawer
async function openAuditDrawer() {
  document.getElementById("drawer-overlay").classList.add("open");
  document.getElementById("audit-drawer").classList.add("open");
  await refreshAuditLogs();
}

function closeAuditDrawer() {
  document.getElementById("drawer-overlay").classList.remove("open");
  document.getElementById("audit-drawer").classList.remove("open");
}

async function refreshAuditLogs() {
  const container = document.getElementById("audit-list");
  container.innerHTML = `<div style="color: #64748b; font-size:12px;">Loading recent audit logs...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/v1/audit/logs`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    if (!res.ok) throw new Error("Could not fetch audit logs");
    const logs = await res.json();

    if (logs.length === 0) {
      container.innerHTML = `<div style="color: #64748b; font-size:12px;">No audit events recorded yet.</div>`;
      return;
    }

    container.innerHTML = logs
      .slice()
      .reverse()
      .map(
        (log) => `
        <div class="audit-item">
          <div class="audit-top">
            <span class="audit-cmd">${escapeHtml(log.command)}</span>
            <span class="badge ${log.status === "SUCCESS" ? "badge-success" : "badge-blocked"}">${log.status}</span>
          </div>
          <div class="audit-meta">
            <span>User: <strong>${escapeHtml(log.username)}</strong></span>
            <span>Namespace: <strong>${escapeHtml(log.namespace)}</strong></span>
            <span>Duration: ${log.duration_ms}ms</span>
          </div>
          ${log.detail ? `<div style="font-size:10px; color:#ef4444; margin-top:4px;">${escapeHtml(log.detail)}</div>` : ""}
          <div style="font-size:10px; color:#475569; margin-top:2px;">${new Date(log.timestamp).toLocaleTimeString()}</div>
        </div>
      `
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<div style="color:#ef4444; font-size:12px;">Error: ${err.message}</div>`;
  }
}

// Simple output syntax highlighter
function highlightKubectlOutput(text) {
  if (!text) return "";
  const lines = text.split("\n");
  return lines
    .map((line, idx) => {
      if (idx === 0 && line.includes("NAME") && (line.includes("READY") || line.includes("TYPE"))) {
        return `<span style="color:#64748b; font-weight:700;">${escapeHtml(line)}</span>`;
      }
      return escapeHtml(line)
        .replace(/\bRunning\b/g, '<span style="color:#10b981; font-weight:600;">Running</span>')
        .replace(/\bClusterIP\b/g, '<span style="color:#38bdf8;">ClusterIP</span>')
        .replace(/\bNodePort\b/g, '<span style="color:#f59e0b;">NodePort</span>')
        .replace(/\bLoadBalancer\b/g, '<span style="color:#a855f7;">LoadBalancer</span>')
        .replace(/\bCrashLoopBackOff\b/g, '<span style="color:#ef4444; font-weight:700;">CrashLoopBackOff</span>')
        .replace(/\bError\b/g, '<span style="color:#ef4444; font-weight:700;">Error</span>')
        .replace(/\bPending\b/g, '<span style="color:#f59e0b;">Pending</span>');
    })
    .join("\n");
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
