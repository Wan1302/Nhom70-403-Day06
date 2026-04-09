const state = {
  sessionId: null,
  loading: false,
};

const el = {
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  chatMessages: document.getElementById("chat-messages"),
  chatStatus: document.getElementById("chat-status"),
  newSessionBtn: document.getElementById("new-session-btn"),
  sessionPill: document.getElementById("session-id-pill"),
  flowPill: document.getElementById("flow-pill"),
  heroIntent: document.getElementById("hero-intent"),
  heroTripSteps: document.getElementById("hero-trip-steps"),
  heroTokens: document.getElementById("hero-tokens"),
  heroLatency: document.getElementById("hero-latency"),
  statSteps: document.getElementById("stat-steps"),
  statInput: document.getElementById("stat-input"),
  statOutput: document.getElementById("stat-output"),
  statLatency: document.getElementById("stat-latency"),
  traceList: document.getElementById("trace-list"),
  metricsTable: document.getElementById("metrics-table"),
  snapshotView: document.getElementById("snapshot-view"),
  promptChips: Array.from(document.querySelectorAll(".prompt-chip")),
};

function appendMessage(role, content) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.textContent = content;
  el.chatMessages.appendChild(message);
  el.chatMessages.scrollTop = el.chatMessages.scrollHeight;
}

function renderTrace(trace = []) {
  el.traceList.innerHTML = "";
  if (!trace.length) {
    el.traceList.innerHTML = `<div class="trace-item"><div class="trace-title">Chưa có dữ liệu</div><div class="trace-detail">Gửi một tin nhắn để xem luồng xử lý.</div></div>`;
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
    el.metricsTable.innerHTML = `<tr><td colspan="5">Chưa có metrics cho lượt chat này.</td></tr>`;
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

function renderSummary(summary = {}, route = {}) {
  el.sessionPill.textContent = state.sessionId ? state.sessionId.slice(0, 8) : "Chưa có";
  el.flowPill.textContent = route.intent || summary.active_flow || "Chưa có luồng";
  el.heroIntent.textContent = route.intent || "-";
  el.heroTripSteps.textContent = summary.trip_step_count ?? 0;
  el.heroTokens.textContent = summary.total_tokens ?? 0;
  el.heroLatency.textContent = `${summary.total_elapsed_ms ?? 0} ms`;

  el.statSteps.textContent = summary.total_steps ?? 0;
  el.statInput.textContent = summary.total_input_tokens ?? 0;
  el.statOutput.textContent = summary.total_output_tokens ?? 0;
  el.statLatency.textContent = `${summary.total_elapsed_ms ?? 0} ms`;
}

function renderSnapshot(snapshot = {}) {
  el.snapshotView.textContent = JSON.stringify(snapshot, null, 2);
}

async function createSession() {
  el.chatStatus.textContent = "Đang tạo phiên...";
  const response = await fetch("/api/session", { method: "POST" });
  const data = await response.json();
  state.sessionId = data.session_id;
  renderSummary(data.summary, {});
  renderSnapshot(data.snapshot);
  renderTrace([]);
  renderMetrics([]);
  el.chatMessages.innerHTML = "";
  appendMessage("assistant", "Xin chào, mình là trợ lý cư dân Vinhomes. Bạn có thể hỏi FAQ, tạo ticket hoặc lên kế hoạch đi chơi ở Ocean Park.");
  el.chatStatus.textContent = "Sẵn sàng";
}

async function sendMessage(message) {
  if (!state.sessionId || state.loading) return;
  state.loading = true;
  el.chatStatus.textContent = "Agent đang xử lý...";

  appendMessage("user", message);
  el.chatInput.value = "";

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: state.sessionId,
      message,
    }),
  });

  const data = await response.json();
  appendMessage("assistant", data.reply);
  renderTrace(data.trace);
  renderMetrics(data.latest_metrics);
  renderSummary(data.summary, data.route);
  renderSnapshot(data.snapshot);
  el.chatStatus.textContent = "Sẵn sàng";
  state.loading = false;
}

el.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = el.chatInput.value.trim();
  if (!message) return;
  try {
    await sendMessage(message);
  } catch (error) {
    appendMessage("assistant", "Đã xảy ra lỗi khi gọi agent. Bạn kiểm tra terminal backend giúp mình nhé.");
    el.chatStatus.textContent = "Có lỗi";
    state.loading = false;
  }
});

el.newSessionBtn.addEventListener("click", async () => {
  await createSession();
});

el.promptChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    el.chatInput.value = chip.dataset.prompt || "";
    el.chatInput.focus();
  });
});

createSession();
