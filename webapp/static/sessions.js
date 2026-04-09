const state = {
  sessions: [],
  activeSessionId: null,
};

const el = {
  newSessionBtn: document.getElementById("new-session-btn"),
  sessionList: document.getElementById("session-list"),
  sessionMeta: document.getElementById("session-meta"),
  openChatLink: document.getElementById("open-chat-link"),
  statSteps: document.getElementById("stat-steps"),
  statInput: document.getElementById("stat-input"),
  statOutput: document.getElementById("stat-output"),
  statLatency: document.getElementById("stat-latency"),
  traceList: document.getElementById("trace-list"),
  metricsTable: document.getElementById("metrics-table"),
  snapshotView: document.getElementById("snapshot-view"),
  pingIndicator: document.getElementById("ping-indicator"),
  pingText: document.getElementById("ping-text"),
};

function formatDate(value) {
  if (!value) return "Chưa có";
  return new Date(value).toLocaleString("vi-VN");
}

function setPing(status, text) {
  el.pingIndicator.className = `ping-dot ${status}`;
  el.pingText.textContent = text;
}

async function checkPing() {
  try {
    const response = await fetch("/api/ping");
    const data = await response.json();
    setPing(data.ok ? "ping-dot-ok" : "ping-dot-bad", data.message || "pong");
  } catch {
    setPing("ping-dot-bad", "Mất kết nối");
  }
}

function renderTrace(trace = []) {
  el.traceList.innerHTML = "";
  if (!trace.length) {
    el.traceList.innerHTML = `<div class="trace-item"><div class="trace-title">Chưa có trace</div><div class="trace-detail">Chọn một phiên đã chat để xem luồng xử lý gần nhất.</div></div>`;
    return;
  }
  trace.forEach((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = "trace-item";
    wrapper.innerHTML = `
      <div class="trace-top">
        <span class="trace-step">${item.step}</span>
        <span class="trace-kind">${item.kind}</span>
      </div>
      <div class="trace-title">${item.title}</div>
      <div class="trace-detail">${item.detail}</div>
    `;
    el.traceList.appendChild(wrapper);
  });
}

function renderMetrics(metrics = []) {
  el.metricsTable.innerHTML = "";
  if (!metrics.length) {
    el.metricsTable.innerHTML = `<tr><td colspan="5">Chưa có metrics cho phiên này.</td></tr>`;
    return;
  }
  metrics.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.node}</td>
      <td>${item.elapsed_ms} ms</td>
      <td>${item.input_tokens}</td>
      <td>${item.output_tokens}</td>
      <td>${item.total_tokens}</td>
    `;
    el.metricsTable.appendChild(row);
  });
}

function renderSummary(summary = {}, session = {}) {
  el.sessionMeta.textContent = `${session.title || "Cuộc trò chuyện"} • cập nhật ${formatDate(session.updated_at)}`;
  el.statSteps.textContent = summary.total_steps ?? 0;
  el.statInput.textContent = summary.total_input_tokens ?? 0;
  el.statOutput.textContent = summary.total_output_tokens ?? 0;
  el.statLatency.textContent = `${summary.total_elapsed_ms ?? 0} ms`;
  el.openChatLink.href = state.activeSessionId ? `/chat?session_id=${state.activeSessionId}` : "/chat";
}

function renderSnapshot(snapshot = {}) {
  el.snapshotView.textContent = JSON.stringify(snapshot, null, 2);
}

function renderSessionList() {
  el.sessionList.innerHTML = "";
  if (!state.sessions.length) {
    el.sessionList.innerHTML = `<div class="session-item"><div class="session-title">Chưa có phiên nào</div><div class="session-preview">Bấm "Tạo phiên mới" để bắt đầu.</div></div>`;
    return;
  }

  state.sessions.forEach((item) => {
    const button = document.createElement("button");
    button.className = `session-item ${item.session_id === state.activeSessionId ? "active" : ""}`;
    button.innerHTML = `
      <div class="session-item-top">
        <div class="session-title">${item.title || "Cuộc trò chuyện mới"}</div>
        <span class="session-badge">${item.intent || item.active_flow || "chat"}</span>
      </div>
      <div class="session-meta">${formatDate(item.updated_at)}</div>
      <div class="session-preview">${item.last_reply || "Chưa có phản hồi nào."}</div>
    `;
    button.addEventListener("click", async () => openSession(item.session_id));
    el.sessionList.appendChild(button);
  });
}

async function openSession(sessionId) {
  const response = await fetch(`/api/session/${sessionId}`);
  const data = await response.json();
  state.activeSessionId = sessionId;
  renderSessionList();
  renderSummary(data.summary || {}, data.session || {});
  renderSnapshot(data.snapshot || {});
  renderTrace(data.trace || []);
  renderMetrics(data.latest_metrics || []);
}

async function loadSessions() {
  const response = await fetch("/api/sessions");
  const data = await response.json();
  state.sessions = data.sessions || [];
  renderSessionList();
  if (state.sessions.length && !state.activeSessionId) {
    await openSession(state.sessions[0].session_id);
  }
}

async function createSession() {
  const response = await fetch("/api/session", { method: "POST" });
  const data = await response.json();
  window.location.href = `/chat?session_id=${data.session_id}`;
}

el.newSessionBtn.addEventListener("click", async () => {
  await createSession();
});

async function boot() {
  await checkPing();
  setInterval(checkPing, 15000);
  await loadSessions();
}

boot();
