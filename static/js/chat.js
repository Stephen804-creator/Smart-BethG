// Smart BethG - chat page behaviour.
// Talks to the real backend at /api/chat (see routes/chat.py). No mock
// responses live here: if the provider isn't configured or a call fails,
// the backend says so honestly and this file just displays that.
(function () {
  const messagesEl = document.getElementById("messages");
  const promptEl = document.getElementById("prompt");
  const sendBtn = document.getElementById("sendMessage");
  const providerSelect = document.getElementById("providerSelect");
  if (!messagesEl || !promptEl || !sendBtn) return;

  const STORAGE_KEY = "sbg:conversationId";
  const PROVIDER_KEY = "sbg:provider";
  let conversationId = window.localStorage.getItem(STORAGE_KEY) || null;

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
      const available = data.available || [];

      if (available.length === 0) {
        providerSelect.style.display = "none";
        return;
      }
      if (available.length === 1) {
        providerSelect.style.display = "none";
      }

      providerSelect.innerHTML = "";
      available.forEach((name) => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name.charAt(0).toUpperCase() + name.slice(1);
        providerSelect.appendChild(opt);
      });

      const saved = window.localStorage.getItem(PROVIDER_KEY);
      providerSelect.value = available.includes(saved) ? saved : (data.default || available[0]);

      providerSelect.addEventListener("change", () => {
        window.localStorage.setItem(PROVIDER_KEY, providerSelect.value);
      });
    } catch (err) {
      // Silent: chat still works with the backend's default provider.
    }
  }

  function renderMessage(role, content) {
    const wrapper = document.createElement("div");
    wrapper.className = "message " + (role === "user" ? "message-user" : "message-assistant");

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = role === "user" ? "You" : "Smart BethG";
    wrapper.appendChild(meta);

    const body = document.createElement("div");
    body.textContent = content;
    wrapper.appendChild(body);

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
          provider: providerSelect && providerSelect.value ? providerSelect.value : null,
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
      renderMessage("assistant", data.reply);
    } catch (err) {
      if (messagesEl.lastChild) messagesEl.lastChild.remove();
      renderNotice("Could not reach Smart BethG. Check your connection and try again.");
    } finally {
      sendBtn.disabled = false;
      promptEl.disabled = false;
      promptEl.focus();
    }
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
})();
