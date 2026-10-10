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
        card.style.cssText = "padding:12px; border:1px solid var(--border); border-radius:10px;";
        const title = document.createElement("strong");
        title.textContent = approval.action || "Restricted action";
        const resource = document.createElement("p");
        resource.style.cssText = "margin:6px 0 10px; font-size:13px; overflow-wrap:anywhere;";
        resource.textContent = "Resource: " + (approval.resource || "not specified");
        const actions = document.createElement("div");
        actions.style.cssText = "display:flex; gap:8px; flex-wrap:wrap;";
        const approve = document.createElement("button");
        approve.type = "button";
        approve.className = "btn";
        approve.textContent = "Approve";
        const reject = document.createElement("button");
        reject.type = "button";
        reject.className = "btn";
        reject.textContent = "Reject";
        reject.style.background = "var(--surface-hover, transparent)";
        reject.addEventListener("click", () => decideApproval(approval.id, false));
        approve.addEventListener("click", () => decideApproval(approval.id, true));
        actions.append(approve, reject);
        card.append(title, resource, actions);
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
      const res = await fetch("/approvals/" + encodeURIComponent(approvalId), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await res.json();
      if (!res.ok || data.error) {
        if (status) status.textContent = data.detail || data.error || "Could not save your decision.";
        return;
      }
      if (status) status.textContent = approved
        ? "Approval recorded. The action has not necessarily run yet."
        : "Action rejected.";
      await loadApprovals();
    } catch (err) {
      if (status) status.textContent = "Could not reach the server. Your decision may not have been saved.";
    }
  }

  async function loadConversationList() {
    if (!conversationListEl) return;
    try {
      const res = await fetch("/api/chat/conversations", { credentials: "same-origin" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) return;
      const data = await res.json();
      renderConversationList(data.conversations || []);
    } catch (err) {
      // Silent: history is a convenience, chat still works without it.
    }
  }

  function renderConversationList(conversations) {
    conversationListEl.innerHTML = "";
    if (conversations.length === 0) {
      const empty = document.createElement("p");
      empty.style.cssText = "color:var(--text-secondary); font-size:13px; padding:6px 8px;";
      empty.textContent = "No conversations yet.";
      conversationListEl.appendChild(empty);
      return;
    }
    conversations.forEach((c) => {
      const item = document.createElement("button");
      item.type = "button";
      const isActive = String(c.id) === String(conversationId);
      item.style.cssText =
        "display:block; width:100%; text-align:left; padding:9px 10px; border-radius:8px; " +
        "border:none; background:" + (isActive ? "var(--surface-hover, rgba(255,255,255,0.08))" : "transparent") +
        "; color:var(--text-primary); font-size:13px; cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;";
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
      if (!res.ok) return;
      const data = await res.json();
      const catalog = data.catalog || {};
      const providerNames = Object.keys(catalog);

      if (providerNames.length === 0) {
        providerSelect.style.display = "none";
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
      // Silent: chat still works with the backend's Auto selection.
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
      noteEl.style.cssText = "font-size:12px; color:var(--text-secondary); margin-top:4px; opacity:0.8;";
      noteEl.textContent = note;
      wrapper.appendChild(noteEl);
    }

    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderNotice(text) {
    const notice = document.createElement("div");
    notice.className = "message message-assistant";
    notice.style.opacity = "0.7";
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
      if (!res.ok) return;
      const data = await res.json();
      (data.messages || []).forEach((m) => renderMessage(m.role, m.content));
    } catch (err) {
      // Silent: an empty history is a fine starting state.
    }
  }

  async function sendMessage(text) {
    renderMessage("user", text);
    sendBtn.disabled = true;
    promptEl.disabled = true;
    renderNotice("Thinking...");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
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
        renderNotice("Something went wrong sending that message. Please try again.");
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
      renderNotice("Could not reach Smart BethG. Check your connection and try again.");
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
