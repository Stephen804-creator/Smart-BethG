// Smart BethG - chat page behaviour.
// Talks to the real backend at /api/chat (see routes/chat.py). No mock
// responses live here: if the provider isn't configured or a call fails,
// the backend says so honestly and this file just displays that.
(function () {
  const messagesEl = document.getElementById("messages");
  const promptEl = document.getElementById("prompt");
  const sendBtn = document.getElementById("sendMessage");
  const providerSelect = document.getElementById("providerSelect");
  const conversationListEl = document.getElementById("conversationList");
  const newChatBtn = document.getElementById("newChatButton");
  if (!messagesEl || !promptEl || !sendBtn) return;

  const STORAGE_KEY = "sbg:conversationId";
  const SELECTION_KEY = "sbg:selection";
  let conversationId = window.localStorage.getItem(STORAGE_KEY) || null;

  async function getCsrfToken() {
    const res = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!res.ok) throw new Error("Could not obtain CSRF token.");
    const data = await res.json();
    if (!data.csrf_token) throw new Error("CSRF token missing.");
    return data.csrf_token;
  }

  async function loadApprovals() {
    const panel = document.getElementById("approvalPanel");
    const list = document.getElementById("approvalList");
    const status = document.getElementById("approvalStatus");
    if (!panel || !list) return;

    try {
      const res = await fetch("/approvals", { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error("Unable to load pending approvals.");
      const approvals = await res.json();
      list.replaceChildren();
      panel.style.display = approvals.length ? "block" : "none";
      if (status) status.textContent = "";

      approvals.forEach((approval) => {
        const card = document.createElement("article");
        card.className = "approval-card approval-request";
        const title = document.createElement("strong");
        title.textContent = approval.action || "Restricted action";
        const resource = document.createElement("p");
        resource.className = "approval-resource";
        resource.textContent = "Resource: " + (approval.resource || "not specified");
        const details = document.createElement("details");
        details.className = "approval-details";
        const detailsSummary = document.createElement("summary");
        detailsSummary.textContent = "Review exact operation arguments";
        const detailsBody = document.createElement("pre");
        detailsBody.className = "approval-payload";
        detailsBody.textContent = JSON.stringify(approval.payload || {}, null, 2);
        details.append(detailsSummary, detailsBody);

        const actions = document.createElement("div");
        actions.className = "approval-actions";
        const approve = document.createElement("button");
        approve.type = "button";
        approve.className = "btn btn-primary";
        approve.textContent = "Approve";
        const reject = document.createElement("button");
        reject.type = "button";
        reject.className = "btn btn-secondary";
        reject.textContent = "Reject";
        
        reject.addEventListener("click", () => decideApproval(approval.id, false));
        approve.addEventListener("click", () => decideApproval(approval.id, true));
        actions.append(approve, reject);
        card.append(title, resource, details, actions);
        list.appendChild(card);
      });
    } catch (err) {
      panel.style.display = "block";
      list.replaceChildren();
      if (status) status.textContent = "Could not load approvals. Refresh the page and try again.";
    }
  }

  async function decideApproval(approvalId, approved) {
    const status = document.getElementById("approvalStatus");
    if (status) status.textContent = "Saving your decision…";
    try {
      const csrfToken = await getCsrfToken();
      const res = await fetch("/approvals/" + encodeURIComponent(approvalId), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ approved }),
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await res.json();
      if (!res.ok || data.error) {
        const errorMessage = (data.error && data.error.message) || data.detail || data.error || "Could not save your decision.";
        if (status) status.textContent = String(errorMessage);
        return;
      }
      if (status) {
        if (!approved) {
          status.textContent = "Action rejected. It will not be executed.";
        } else {
          const execution = data.execution;
          if (execution && execution.success) {
            status.textContent = "Approved and executed successfully.";
          } else if (execution) {
            status.textContent = "Approval recorded, but execution status is " +
              (execution.execution_status || execution.status || "unknown") + ". Review the result before retrying.";
          } else {
            status.textContent = "Approval recorded.";
          }
        }
      }
      await loadApprovals();
    } catch (err) {
      if (status) status.textContent = "Could not reach the server. Your decision may not have been saved.";
    }
  }

  function showStatus(status, message, retryLabel, retryAction) {
    if (!status) return;
    status.replaceChildren();
    const messageEl = document.createElement("span");
    messageEl.textContent = message;
    status.appendChild(messageEl);
    if (retryLabel && typeof retryAction === "function") {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "status-retry-button";
      retry.textContent = retryLabel;
      retry.addEventListener("click", retryAction);
      status.appendChild(retry);
    }
  }

  async function loadConversationList() {
    if (!conversationListEl) return;
    const status = document.getElementById("conversationStatus");
    if (status) status.replaceChildren();
    try {
      const res = await fetch("/api/chat/conversations", { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error("Conversation history request failed.");
      const data = await res.json();
      renderConversationList(data.conversations || []);
      if (status) status.replaceChildren();
    } catch (err) {
      showStatus(status, "Conversation history couldn't load. You can still start a new chat.", "Retry", loadConversationList);
    }
  }

  function renderConversationList(conversations) {
    conversationListEl.innerHTML = "";
    if (conversations.length === 0) {
      const empty = document.createElement("p");
      empty.className = "conversation-empty";
      empty.textContent = "No conversations yet.";
      conversationListEl.appendChild(empty);
      return;
    }
    conversations.forEach((c) => {
      const item = document.createElement("button");
      item.type = "button";
      const isActive = String(c.id) === String(conversationId);
      item.className = "conversation-item" + (isActive ? " is-active" : "");
      item.textContent = c.title || "New conversation";
      item.addEventListener("click", () => switchConversation(c.id));
      conversationListEl.appendChild(item);
    });
  }

  function switchConversation(id) {
    conversationId = id;
    window.localStorage.setItem(STORAGE_KEY, conversationId);
    messagesEl.innerHTML = "";
    loadHistory();
    loadConversationList();
  }

  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      conversationId = null;
      window.localStorage.removeItem(STORAGE_KEY);
      messagesEl.innerHTML = "";
      promptEl.focus();
      loadConversationList();
    });
  }

  async function loadProviders() {
    if (!providerSelect) return;
    try {
      const res = await fetch("/api/chat/providers", { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error("Provider catalog request failed.");
      const data = await res.json();
      const catalog = data.catalog || {};
      const providerNames = Object.keys(catalog);

      const providerStatus = document.getElementById("providerStatus");
      if (providerNames.length === 0) {
        providerSelect.hidden = true;
        if (providerStatus) {
          providerStatus.hidden = false;
          showStatus(providerStatus, "No provider choices are available. Chat will use the server's default routing.", "Check again", loadProviders);
        }
        return;
      }

      providerSelect.innerHTML = "";

      const autoOpt = document.createElement("option");
      autoOpt.value = "auto";
      autoOpt.textContent = "Auto";
      providerSelect.appendChild(autoOpt);

      providerNames.forEach((providerName) => {
        const group = document.createElement("optgroup");
        group.label = catalog[providerName].label;
        (catalog[providerName].models || []).forEach((m) => {
          const opt = document.createElement("option");
          opt.value = `${providerName}:${m.id}`;
          opt.textContent = m.label;
          group.appendChild(opt);
        });
        providerSelect.appendChild(group);
      });

      const saved = window.localStorage.getItem(SELECTION_KEY);
      providerSelect.value = saved && [...providerSelect.options].some((o) => o.value === saved)
        ? saved
        : "auto";

      providerSelect.addEventListener("change", () => {
        window.localStorage.setItem(SELECTION_KEY, providerSelect.value);
      });
    } catch (err) {
      const providerStatus = document.getElementById("providerStatus");
      if (providerStatus) {
        providerStatus.hidden = false;
        showStatus(providerStatus, "Provider choices couldn't load. You can still try chat using the server's default routing.", "Retry", loadProviders);
      }
    }
  }

  function renderMessage(role, content, note) {
    const wrapper = document.createElement("div");
    wrapper.className = "message " + (role === "user" ? "message-user" : "message-assistant");

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = role === "user" ? "You" : "Smart BethG";
    wrapper.appendChild(meta);

    const body = document.createElement("div");
    body.textContent = content;
    wrapper.appendChild(body);

    if (note) {
      const noteEl = document.createElement("div");
      noteEl.className = "message-note";
      noteEl.textContent = note;
      wrapper.appendChild(noteEl);
    }

    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderNotice(text) {
    const notice = document.createElement("div");
    notice.className = "message message-assistant";
    notice.classList.add("message-notice");
    notice.textContent = text;
    messagesEl.appendChild(notice);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function loadHistory() {
    if (!conversationId) return;
    try {
      const res = await fetch(`/api/chat/${conversationId}`, { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error("Conversation messages request failed.");
      const data = await res.json();
      (data.messages || []).forEach((m) => renderMessage(m.role, m.content));
      const status = document.getElementById("conversationStatus");
      if (status) status.replaceChildren();
    } catch (err) {
      const status = document.getElementById("conversationStatus");
      showStatus(status, "This conversation couldn't be loaded.", "Retry", loadHistory);
    }
  }

  async function sendMessage(text) {
    renderMessage("user", text);
    sendBtn.disabled = true;
    promptEl.disabled = true;
    renderNotice("Thinking...");

    try {
      const csrfToken = await getCsrfToken();
      const res = await fetch("/api/chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          selection: providerSelect && providerSelect.value ? providerSelect.value : "auto",
        }),
      });

      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }

      messagesEl.lastChild.remove(); // remove "Thinking..." notice

      if (!res.ok) {
        promptEl.value = text;
        renderNotice("Something went wrong sending that message. Your text is back in the composer so you can retry.");
        return;
      }

      const data = await res.json();
      conversationId = data.conversation_id;
      window.localStorage.setItem(STORAGE_KEY, conversationId);
      renderMessage("assistant", data.reply, buildNote(data));
      loadConversationList();
      loadApprovals();
    } catch (err) {
      if (messagesEl.lastChild) messagesEl.lastChild.remove();
      promptEl.value = text;
      renderNotice("Could not reach Smart BethG. Your text is back in the composer so you can retry.");
    } finally {
      sendBtn.disabled = false;
      promptEl.disabled = false;
      promptEl.focus();
    }
  }

  function buildNote(data) {
    // Surfaces state that used to be silently dropped: which provider
    // actually answered (if it wasn't the one requested) and whether an
    // action is now sitting pending approval, rather than just showing
    // the reply text with no indication anything unusual happened.
    const parts = [];
    if (data.fallback_used && data.provider) {
      parts.push(`switched to ${data.provider} after the requested provider failed`);
    }
    if (data.intent && data.intent !== "chat") {
      parts.push(`action: ${data.intent}`);
    }
    return parts.length ? parts.join(" · ") : null;
  }

  function handleSend() {
    const text = promptEl.value.trim();
    if (!text) return;
    promptEl.value = "";
    sendMessage(text);
  }

  sendBtn.addEventListener("click", handleSend);
  promptEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  const params = new URLSearchParams(window.location.search);
  const prefill = params.get("prompt");
  if (prefill) promptEl.value = prefill;

  loadProviders();
  loadHistory();
  loadConversationList();
  loadApprovals();
})();
