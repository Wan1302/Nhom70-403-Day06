const appState = {
  sessionId: null,
  sessions: [],
  loading: false,
};

const $ = {
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  chatMessages: document.getElementById("chat-messages"),
  chatStatus: document.getElementById("chat-status"),
  newSessionBtn: document.getElementById("new-session-btn"),
  sessionList: document.getElementById("session-list"),
  flowPill: document.getElementById("flow-pill"),
  sessionMeta: document.getElementById("session-meta"),
  pingIndicator: document.getElementById("ping-indicator"),
  pingText: document.getElementById("ping-text"),
  promptChips: Array.from(document.querySelectorAll(".prompt-chip")),
  workspaceActions: document.querySelector(".workspace-actions"),
};

$.clearChatBtn = document.getElementById("clear-chat-btn");

if (!$.clearChatBtn && $.workspaceActions) {
  $.clearChatBtn = document.createElement("button");
  $.clearChatBtn.id = "clear-chat-btn";
  $.clearChatBtn.type = "button";
  $.clearChatBtn.className = "ghost-button clear-chat-button";
  $.clearChatBtn.textContent = "Xóa lịch sử chat";
  $.workspaceActions.appendChild($.clearChatBtn);
}

function formatDate(value) {
  if (!value) return "Chưa có";
  return new Date(value).toLocaleString("vi-VN");
}

function setPing(status, text) {
  $.pingIndicator.className = `ping-dot ${status}`;
  $.pingText.textContent = text;
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

function decorateAssistantHtml(container) {
  container.querySelectorAll("a").forEach((a) => {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
  });
}

function createFeedbackBar(meta = {}) {
  if (!meta.sessionId || !meta.question || !meta.answer) return null;

  const actions = document.createElement("div");
  actions.className = "message-feedback";
  actions.dataset.question = meta.question;
  actions.dataset.answer = meta.answer;
  actions.dataset.sessionId = meta.sessionId;

  const buttons = [
    { value: "like", label: "👍 Hữu ích" },
    { value: "dislike", label: "👎 Chưa đúng" },
  ];

  buttons.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "feedback-btn";
    button.dataset.feedback = item.value;
    button.textContent = item.label;
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await submitFeedback(actions, item.value);
    });
    actions.appendChild(button);
  });

  return actions;
}

function appendMessage(role, content, meta = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = "message-block";

  const item = document.createElement("div");
  item.className = `message ${role}`;
  if (role === "assistant" && window.marked) {
    item.innerHTML = marked.parse(content);
    decorateAssistantHtml(item);
  } else {
    item.textContent = content;
  }

  wrapper.appendChild(item);

  if (role === "assistant") {
    const feedbackBar = createFeedbackBar(meta);
    if (feedbackBar) {
      wrapper.appendChild(feedbackBar);
    }
  }

  $.chatMessages.appendChild(wrapper);
  $.chatMessages.scrollTop = $.chatMessages.scrollHeight;
  return wrapper;
}

async function submitFeedback(container, feedbackValue) {
  if (container.dataset.submitting === "true" || container.dataset.selectedFeedback) return;
  container.dataset.submitting = "true";

  try {
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: container.dataset.sessionId,
        question: container.dataset.question,
        answer: container.dataset.answer,
        feedback: feedbackValue,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    container.dataset.selectedFeedback = feedbackValue;
    container.querySelectorAll(".feedback-btn").forEach((button) => {
      const isSelected = button.dataset.feedback === feedbackValue;
      button.disabled = true;
      if (isSelected) {
        button.classList.add("selected");
      }
    });

    const note = document.createElement("span");
    note.className = "feedback-note";
    note.textContent = feedbackValue === "like" ? "Đã ghi nhận phản hồi tích cực" : "Đã ghi nhận cần cải thiện";
    container.appendChild(note);
  } catch {
    const note = document.createElement("span");
    note.className = "feedback-note error";
    note.textContent = "Chưa lưu được phản hồi, bạn thử lại nhé.";
    container.appendChild(note);
  } finally {
    container.dataset.submitting = "false";
  }
}

function renderMessages(messages = []) {
  $.chatMessages.innerHTML = "";
  if (!messages.length) {
    appendMessage("assistant", "Xin chào, mình là trợ lý cư dân Vinhomes. Bạn có thể hỏi FAQ, tạo ticket hoặc lên kế hoạch đi chơi ở Ocean Park.");
    return;
  }

  let lastUserMessage = "";
  messages.forEach((msg) => {
    if (msg.role === "user") {
      lastUserMessage = msg.content;
      appendMessage("user", msg.content);
      return;
    }

    appendMessage("assistant", msg.content, {
      sessionId: appState.sessionId,
      question: lastUserMessage,
      answer: msg.content,
    });
  });
}

function renderSummary(summary = {}, session = {}) {
  $.flowPill.textContent = summary.intent || summary.active_flow || "Chưa có luồng";
  $.sessionMeta.textContent = `${session.title || "Cuộc trò chuyện"} • cập nhật ${formatDate(session.updated_at)}`;
}

function renderSessionList() {
  $.sessionList.innerHTML = "";
  if (!appState.sessions.length) {
    $.sessionList.innerHTML = `<div class="session-item"><div class="session-title">Chưa có phiên nào</div><div class="session-preview">Bấm "Cuộc trò chuyện mới" để bắt đầu.</div></div>`;
    return;
  }

  appState.sessions.forEach((item) => {
    const card = document.createElement("div");
    card.className = `session-item ${item.session_id === appState.sessionId ? "active" : ""} ${item.pinned ? "pinned" : ""}`;
    card.innerHTML = `
      <div class="session-item-top">
        <div class="session-title">${item.title || "Cuộc trò chuyện mới"}</div>
        <span class="session-badge">${item.intent || item.active_flow || "chat"}</span>
      </div>
      <div class="session-meta">${formatDate(item.updated_at)}</div>
      <div class="session-preview">${item.last_reply || "Chưa có phản hồi nào."}</div>
    `;

    card.addEventListener("click", async () => openSession(item.session_id));

    if (item.pinned) {
      const titleNode = card.querySelector(".session-title");
      if (titleNode) titleNode.textContent = `📌 ${titleNode.textContent}`;
    }

    const actions = document.createElement("div");
    actions.className = "session-actions";
    actions.innerHTML = `
      <button class="session-action-btn" type="button" data-action="pin">${item.pinned ? "Bỏ ghim" : "Ghim"}</button>
      <button class="session-action-btn" type="button" data-action="rename">Đổi tên</button>
      <button class="session-action-btn" type="button" data-action="clear">X.chat</button>
      <button class="session-action-btn warn" type="button" data-action="delete">X.phiên</button>
    `;

    actions.querySelector('[data-action="pin"]').addEventListener("click", async (event) => {
      event.stopPropagation();
      await togglePinned(item);
    });
    actions.querySelector('[data-action="rename"]').addEventListener("click", async (event) => {
      event.stopPropagation();
      await renameSession(item);
    });
    actions.querySelector('[data-action="clear"]').addEventListener("click", async (event) => {
      event.stopPropagation();
      await clearSessionFromList(item);
    });
    actions.querySelector('[data-action="delete"]').addEventListener("click", async (event) => {
      event.stopPropagation();
      await deleteSessionFromList(item);
    });

    card.appendChild(actions);
    $.sessionList.appendChild(card);
  });
}

async function refreshSessions() {
  const response = await fetch("/api/sessions");
  const data = await response.json();
  appState.sessions = data.sessions || [];
  renderSessionList();
}

async function createSession() {
  $.chatStatus.textContent = "Đang tạo phiên...";
  const response = await fetch("/api/session", { method: "POST" });
  const data = await response.json();
  appState.sessionId = data.session_id;
  await refreshSessions();
  history.replaceState({}, "", `/chat?session_id=${appState.sessionId}`);
  renderMessages([]);
  renderSummary(data.summary || {}, data.session || {});
  $.chatStatus.textContent = "Sẵn sàng";
}

async function openSession(sessionId) {
  const response = await fetch(`/api/session/${sessionId}`);
  const data = await response.json();
  appState.sessionId = sessionId;
  history.replaceState({}, "", `/chat?session_id=${appState.sessionId}`);
  renderMessages(data.messages || []);
  renderSummary(data.summary || {}, data.session || {});
  renderSessionList();
}

async function patchSessionMeta(sessionId, payload) {
  const response = await fetch(`/api/session/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function togglePinned(item) {
  await patchSessionMeta(item.session_id, { pinned: !item.pinned });
  await refreshSessions();
  if (item.session_id === appState.sessionId) {
    await openSession(item.session_id);
  }
}

async function renameSession(item) {
  const nextTitle = window.prompt("Nhập tên phiên mới:", item.title || "");
  if (!nextTitle || !nextTitle.trim()) return;
  await patchSessionMeta(item.session_id, { title: nextTitle.trim() });
  await refreshSessions();
  if (item.session_id === appState.sessionId) {
    await openSession(item.session_id);
  }
}

async function clearSessionFromList(item) {
  const confirmed = window.confirm(`Xóa toàn bộ lịch sử chat của phiên "${item.title}"?`);
  if (!confirmed) return;
  await fetch(`/api/session/${item.session_id}/clear`, { method: "POST" });
  await refreshSessions();
  if (item.session_id === appState.sessionId) {
    await openSession(item.session_id);
    $.chatStatus.textContent = "Đã xóa lịch sử phiên";
  }
}

async function deleteSessionFromList(item) {
  const confirmed = window.confirm(`Xóa hẳn phiên "${item.title}"?`);
  if (!confirmed) return;
  await fetch(`/api/session/${item.session_id}`, { method: "DELETE" });
  if (item.session_id === appState.sessionId) {
    appState.sessionId = null;
  }
  await refreshSessions();
  if (appState.sessions.length) {
    await openSession(appState.sessions[0].session_id);
  } else {
    await createSession();
  }
}

async function clearCurrentSession() {
  if (!appState.sessionId || appState.loading) return;
  const confirmed = window.confirm("Bạn muốn xóa toàn bộ lịch sử chat của phiên hiện tại chứ?");
  if (!confirmed) return;

  appState.loading = true;
  $.chatStatus.textContent = "Đang xóa lịch sử chat...";

  try {
    const response = await fetch(`/api/session/${appState.sessionId}/clear`, {
      method: "POST",
    });
    const data = await response.json();
    renderMessages(data.messages || []);
    renderSummary(data.summary || {}, data.session || {});
    await refreshSessions();
    $.chatStatus.textContent = "Đã xóa lịch sử chat";
  } catch {
    appendMessage("assistant", "Không thể xóa lịch sử chat lúc này. Bạn thử lại giúp mình nhé.");
    $.chatStatus.textContent = "Có lỗi";
  } finally {
    appState.loading = false;
  }
}

async function sendMessage(message) {
  if (!appState.sessionId || appState.loading) return;
  appState.loading = true;
  $.chatStatus.textContent = "Agent đang xử lý...";

  appendMessage("user", message);
  $.chatInput.value = "";
  $.chatInput.style.height = "auto";

  const wrapper = document.createElement("div");
  wrapper.className = "message-block";

  const bubble = document.createElement("div");
  bubble.className = "message assistant streaming";
  bubble.innerHTML = `<span class="stream-text"></span><span class="stream-cursor">▋</span>`;
  wrapper.appendChild(bubble);
  $.chatMessages.appendChild(wrapper);
  $.chatMessages.scrollTop = $.chatMessages.scrollHeight;

  const streamText = bubble.querySelector(".stream-text");
  const cursor = bubble.querySelector(".stream-cursor");

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: appState.sessionId, message }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let lastEventType = "message";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith("event:")) {
          lastEventType = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          const raw = line.slice(5).trim();
          if (!raw) continue;
          try {
            const payload = JSON.parse(raw);

            if (lastEventType === "done" || payload.done) {
              cursor.remove();
              bubble.classList.remove("streaming");

              const finalContent = streamText.textContent;
              if (window.marked) {
                bubble.innerHTML = marked.parse(finalContent);
                decorateAssistantHtml(bubble);
              }

              const feedbackBar = createFeedbackBar({
                sessionId: appState.sessionId,
                question: message,
                answer: finalContent,
              });
              if (feedbackBar) {
                wrapper.appendChild(feedbackBar);
              }

              renderSummary(payload.summary || {}, payload.session || {});
              await refreshSessions();
            } else if (payload.chunk !== undefined) {
              streamText.textContent += payload.chunk;
              $.chatMessages.scrollTop = $.chatMessages.scrollHeight;
            }
          } catch {
          }
          lastEventType = "message";
        }
      }
    }
  } catch {
    cursor.remove();
    bubble.classList.remove("streaming");
    streamText.textContent = "Đã có lỗi khi kết nối đến agent. Bạn kiểm tra backend giúp mình nhé.";
  }

  $.chatStatus.textContent = "Sẵn sàng";
  appState.loading = false;
}

async function submitCurrentMessage() {
  const message = $.chatInput.value.trim();
  if (!message) return;
  try {
    await sendMessage(message);
  } catch {
    appendMessage("assistant", "Đã có lỗi khi gọi agent. Bạn kiểm tra backend giúp mình nhé.");
    $.chatStatus.textContent = "Có lỗi";
    appState.loading = false;
  }
}

$.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitCurrentMessage();
});

$.newSessionBtn.addEventListener("click", async () => {
  await createSession();
});

if ($.clearChatBtn) {
  $.clearChatBtn.addEventListener("click", async () => {
    await clearCurrentSession();
  });
}

$.chatInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await submitCurrentMessage();
  }
});

$.promptChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    $.chatInput.value = chip.dataset.prompt || "";
    $.chatInput.focus();
  });
});

async function boot() {
  await checkPing();
  setInterval(checkPing, 15000);
  await refreshSessions();
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get("session_id");
  if (sessionId) {
    await openSession(sessionId);
    return;
  }
  if (appState.sessions.length) {
    await openSession(appState.sessions[0].session_id);
    return;
  }
  await createSession();
}

boot();
