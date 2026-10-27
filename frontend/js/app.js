/**
 * AWS EKS Web CLI - Client Application
 * Handles authentication, terminal command execution, namespace isolation, and real-time audit logs.
 */

const API_BASE = "";

// State
let authToken = localStorage.getItem("eks_token") || null;
let currentUser = null;
let activeNamespace = "ns-4";
let commandHistory = [];
let historyIndex = -1;

// Predefined demo accounts
const DEMO_USERS = [
  { username: "alice", role: "Developer", namespaces: ["ns-4"] },
  { username: "bob", role: "Payments Team", namespaces: ["application-1"] },
  { username: "carol", role: "Analytics Team", namespaces: ["ns-5", "ns-6"] },
  { username: "dave", role: "Billing Team", namespaces: ["application-2", "application-3"] },
  { username: "qa-user", role: "QA Engineer", namespaces: ["application-8", "application-9"] },
  { username: "devops-viewer", role: "DevOps Viewer", namespaces: ["All Namespaces"] },
];

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await ensureAuthentication();
  printWelcomeBanner();
});

// Setup UI Event Listeners
function setupEventListeners() {
  const cliInput = document.getElementById("cli-input");
  const runBtn = document.getElementById("btn-run-cmd");
  const clearBtn = document.getElementById("btn-clear-term");
  const nsSelect = document.getElementById("ns-select");
  const userBadge = document.getElementById("user-badge");
  const auditBtn = document.getElementById("btn-audit-drawer");
  const closeAuditBtn = document.getElementById("btn-close-audit");
  const drawerOverlay = document.getElementById("drawer-overlay");
  const modalOverlay = document.getElementById("user-modal-overlay");
  const closeModalBtn = document.getElementById("btn-close-modal");

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

  // Namespace selector change
  nsSelect.addEventListener("change", (e) => {
    activeNamespace = e.target.value;
    updateTerminalPrompt();
    printSystemNotice(`Switched active context to namespace: [${activeNamespace}]`);
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

  // User Switcher Modal
  userBadge.addEventListener("click", openUserModal);
  closeModalBtn.addEventListener("click", closeUserModal);
  modalOverlay.addEventListener("click", (e) => {
    if (e.target === modalOverlay) closeUserModal();
  });

  // Audit Drawer
  auditBtn.addEventListener("click", openAuditDrawer);
  closeAuditBtn.addEventListener("click", closeAuditDrawer);
  drawerOverlay.addEventListener("click", closeAuditDrawer);
}

// Authentication
async function ensureAuthentication() {
  // If no token or invalid, default login as Alice (ns-4)
  if (!authToken) {
    await loginUser("alice");
  } else {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        currentUser = await res.json();
        updateUserUI();
      } else {
        await loginUser("alice");
      }
    } catch {
      await loginUser("alice");
    }
  }
}

async function loginUser(username) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });
    if (!res.ok) throw new Error("Authentication failed");
    const data = await res.json();
    authToken = data.access_token;
    currentUser = data.user;
    localStorage.setItem("eks_token", authToken);
    activeNamespace = currentUser.default_namespace;
    updateUserUI();
    printSystemNotice(`Authenticated as [${currentUser.username}]. Authorized namespaces: [${currentUser.allowed_namespaces.join(", ")}]`);
    closeUserModal();
  } catch (err) {
    console.error("Login error:", err);
  }
}

// Update UI with current user permissions & namespace dropdown
function updateUserUI() {
  if (!currentUser) return;

  // Header user info
  document.getElementById("user-name").textContent = currentUser.username;
  document.getElementById("user-avatar").textContent = currentUser.username.charAt(0).toUpperCase();

  // Banner
  document.getElementById("banner-user").textContent = currentUser.username;
  const bannerNsList = document.getElementById("banner-namespaces");
  bannerNsList.innerHTML = currentUser.allowed_namespaces
    .map((ns) => `<span class="ns-chip">${ns}</span>`)
    .join("");

  // Populate Namespace Selector (ONLY with allowed namespaces!)
  const nsSelect = document.getElementById("ns-select");
  nsSelect.innerHTML = currentUser.allowed_namespaces
    .map(
      (ns) =>
        `<option value="${ns}" ${ns === activeNamespace ? "selected" : ""}>${ns}</option>`
    )
    .join("");

  // Ensure active namespace is in user's allowed list
  if (!currentUser.allowed_namespaces.includes(activeNamespace)) {
    activeNamespace = currentUser.allowed_namespaces[0];
    nsSelect.value = activeNamespace;
  }

  updateTerminalPrompt();
}

function updateTerminalPrompt() {
  const promptUser = document.getElementById("prompt-user");
  const promptNs = document.getElementById("prompt-ns");
  if (promptUser && currentUser) promptUser.textContent = currentUser.username;
  if (promptNs) promptNs.textContent = activeNamespace;
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
      // 403 Forbidden or 400 Bad Request
      appendOutputToTerminal(data.detail || "Request failed", true, 0, false);
    } else if (data.error) {
      appendOutputToTerminal(data.error, true, data.duration_ms, false);
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
    contentHtml += `<div class="mock-indicator">Cluster Preview Mode (${durationMs.toFixed(1)}ms)</div>\n`;
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
<span style="color:#38bdf8; font-weight:700;">☸ AWS EKS Scoped Web CLI v1.0.0</span>
Cluster: <span style="color:#e2e8f0;">aws-eks-production</span> | Connection: <span style="color:#10b981;">Active</span>
Namespace Isolation: <span style="color:#a855f7;">Enforced</span> (Strict Least Privilege)

Try commands:
  • <span style="color:#38bdf8;">kubectl get services</span>
  • <span style="color:#38bdf8;">kubectl get pods</span>
  • <span style="color:#38bdf8;">kubectl get endpoints</span>
  • <span style="color:#38bdf8;">kubectl describe service order-service</span>
    </div>
  `;
  termBody.appendChild(welcomeDiv);
}

function printSystemNotice(text) {
  const termBody = document.getElementById("terminal-body");
  const noticeDiv = document.createElement("div");
  noticeDiv.className = "term-entry";
  noticeDiv.innerHTML = `
    <div class="term-output" style="color:#38bdf8; font-size:12px; border-left-color:#38bdf8;">
      ℹ ${escapeHtml(text)}
    </div>
  `;
  termBody.appendChild(noticeDiv);
  scrollTerminalToBottom();
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
    if (data.output) {
      renderServiceCards(data.output);
    }
  } catch (err) {
    container.innerHTML = `<div style="color:#ef4444; font-size:13px;">Failed to load services: ${err.message}</div>`;
  }
}

function renderServiceCards(rawOutput) {
  const container = document.getElementById("visualizer-container");
  const lines = rawOutput.trim().split("\n");
  if (lines.length <= 1) {
    container.innerHTML = `<div style="color:#94a3b8; font-size:13px; grid-column:1/-1;">No services deployed in namespace [${activeNamespace}].</div>`;
    return;
  }

  // Parse lines
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
}

window.runQuickCommand = function (cmd) {
  // Switch to terminal tab
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
  container.innerHTML = `<div style="color:#94a3b8; font-size:12px;">Fetching audit events...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/v1/audit/logs?namespace=${activeNamespace}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    if (!res.ok) throw new Error("Could not fetch audit logs");
    const logs = await res.json();

    if (logs.length === 0) {
      container.innerHTML = `<div style="color:#64748b; font-size:12px;">No audit events recorded yet for [${activeNamespace}].</div>`;
      return;
    }

    container.innerHTML = logs
      .map(
        (l) => `
        <div class="audit-card">
          <div class="audit-header">
            <span style="color:#94a3b8;">${new Date(l.timestamp).toLocaleTimeString()} · ${escapeHtml(l.username)}</span>
            <span class="badge-status ${l.status.toLowerCase()}">${l.status}</span>
          </div>
          <div class="audit-cmd">$ ${escapeHtml(l.command)}</div>
          <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b;">
            <span>ns: ${escapeHtml(l.namespace)}</span>
            <span>${l.duration_ms}ms · IP: ${l.client_ip || "local"}</span>
          </div>
          ${l.detail ? `<div class="audit-detail">${escapeHtml(l.detail)}</div>` : ""}
        </div>
      `
      )
      .join("");
  } catch (err) {
    container.innerHTML = `<div style="color:#ef4444; font-size:12px;">Error: ${err.message}</div>`;
  }
}

// User Switcher Modal
function openUserModal() {
  const listContainer = document.getElementById("user-options-list");
  listContainer.innerHTML = DEMO_USERS.map((u) => {
    const isCurrent = currentUser && currentUser.username === u.username;
    return `
      <button class="user-option-btn ${isCurrent ? "active" : ""}" onclick="switchUser('${u.username}')">
        <div class="user-info-text">
          <strong>${u.username} ${isCurrent ? "(Active)" : ""}</strong>
          <span>Role: ${u.role}</span>
        </div>
        <div style="display:flex; gap:4px; flex-wrap:wrap;">
          ${u.namespaces.map((ns) => `<span class="ns-chip">${ns}</span>`).join("")}
        </div>
      </button>
    `;
  }).join("");

  document.getElementById("user-modal-overlay").classList.add("open");
}

function closeUserModal() {
  document.getElementById("user-modal-overlay").classList.remove("open");
}

window.switchUser = async function (username) {
  await loginUser(username);
  loadVisualizerServices();
};

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
