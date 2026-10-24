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
  let isSending = false;
  const chatToolsButton = document.getElementById("chatToolsButton");
  const chatToolsMenu = document.getElementById("chatToolsMenu");
  const chatFileInput = document.getElementById("chatFileInput");
  const chatImageInput = document.getElementById("chatImageInput");
  const chooseChatFiles = document.getElementById("chooseChatFiles");
  const chooseChatImages = document.getElementById("chooseChatImages");
  const webSearchToggle = document.getElementById("webSearchToggle");
  const chatProjectSelect = document.getElementById("chatProjectSelect");
  const chatAttachmentList = document.getElementById("chatAttachmentList");
  let pendingTextAttachments = [];
  const MAX_ATTACHMENT_BYTES = 200 * 1024;
  const MAX_ATTACHMENT_TOTAL_CHARS = 30000;

  if (chatToolsButton && chatToolsMenu) {
    chatToolsButton.addEventListener("click", () => {
      const willOpen = chatToolsMenu.hidden;
      chatToolsMenu.hidden = !willOpen;
      chatToolsButton.setAttribute("aria-expanded", String(willOpen));
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".chat-tools-menu-wrap")) {
        chatToolsMenu.hidden = true;
        chatToolsButton.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !chatToolsMenu.hidden) {
        chatToolsMenu.hidden = true;
        chatToolsButton.setAttribute("aria-expanded", "false");
        chatToolsButton.focus();
      }
    });
  }
  if (chooseChatFiles && chatFileInput) chooseChatFiles.addEventListener("click", () => chatFileInput.click());
  if (chooseChatImages && chatImageInput) chooseChatImages.addEventListener("click", () => {
    window.alert("Image upload is not connected to the current chat API yet. Choose a text file for now.");
  });

  function renderAttachmentList() {
    if (!chatAttachmentList) return;
    chatAttachmentList.replaceChildren();
    pendingTextAttachments.forEach((item, index) => {
      const chip = document.createElement("span");
      chip.className = "chat-attachment-chip";
      const label = document.createElement("span");
      label.textContent = item.name;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.setAttribute("aria-label", "Remove " + item.name);
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        pendingTextAttachments.splice(index, 1);
        renderAttachmentList();
      });
      chip.append(label, remove);
      chatAttachmentList.appendChild(chip);
    });
  }

  if (chatFileInput) {
    chatFileInput.addEventListener("change", async () => {
      const files = Array.from(chatFileInput.files || []);
      chatFileInput.value = "";
      let total = pendingTextAttachments.reduce((sum, item) => sum + item.content.length, 0);
      for (const file of files) {
        if (file.size > MAX_ATTACHMENT_BYTES) {
          renderNotice(file.name + " is over the 200 KB text-file limit and was skipped.");
          continue;
        }
        if (total >= MAX_ATTACHMENT_TOTAL_CHARS) {
          renderNotice("The attachment text limit has been reached.");
          break;
        }
        try {
          const content = await file.text();
          if (content.includes("\u0000")) {
            renderNotice(file.name + " doesn't look like a text file and was skipped.");
            continue;
          }
          const remaining = MAX_ATTACHMENT_TOTAL_CHARS - total;
          pendingTextAttachments.push({ name: file.name, content: content.slice(0, remaining) });
          total += Math.min(content.length, remaining);
        } catch (_) {
          renderNotice("Couldn't read " + file.name + ".");
        }
      }
      renderAttachmentList();
    });
  }

  async function loadChatProjects() {
    if (!chatProjectSelect) return;
    try {
      const response = await fetch("/api/projects", { credentials: "same-origin" });
      if (response.status === 401) { window.location.href = "/login"; return; }
      if (!response.ok) throw new Error("Project list unavailable");
      const data = await response.json();
      (data.projects || []).filter((project) => project.status !== "archived").forEach((project) => {
        const option = document.createElement("option");
        option.value = String(project.id);
        option.textContent = project.name;
        option.dataset.projectName = project.name;
        chatProjectSelect.appendChild(option);
      });
    } catch (_) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Projects unavailable";
      option.disabled = true;
      chatProjectSelect.appendChild(option);
    }
  }
  loadChatProjects();

  function setConversationControlsBusy(busy) {
    isSending = busy;
    if (newChatBtn) newChatBtn.disabled = busy;
    if (conversationListEl) {
      conversationListEl.querySelectorAll(".conversation-item").forEach((item) => {
        item.disabled = busy;
      });
    }
  }

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
      item.disabled = isSending;
      if (isActive) item.setAttribute("aria-current", "true");
      item.addEventListener("click", () => switchConversation(c.id));
      conversationListEl.appendChild(item);
    });
  }

  function switchConversation(id) {
    if (isSending) return;
    conversationId = id;
    window.localStorage.setItem(STORAGE_KEY, conversationId);
    messagesEl.innerHTML = "";
    loadHistory();
    loadConversationList();
  }

  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      if (isSending) return;
      conversationId = null;
      window.localStorage.removeItem(STORAGE_KEY);
      messagesEl.innerHTML = "";
      renderWelcome();
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

  function renderWelcome() {
    if (messagesEl.querySelector(".chat-welcome")) return;
    const welcome = document.createElement("section");
    welcome.className = "chat-welcome";
    welcome.setAttribute("aria-labelledby", "chatWelcomeTitle");
    const eyebrow = document.createElement("p");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = "YOUR AI WORKSPACE";
    const title = document.createElement("h2");
    title.id = "chatWelcomeTitle";
    title.textContent = "What would you like to work on?";
    const description = document.createElement("p");
    description.className = "chat-welcome-description";
    description.textContent = "Start with an idea, a question, or something you want to build. Choose a starting point or write your own request below.";
    const suggestions = document.createElement("div");
    suggestions.className = "chat-suggestions";
    const options = [
      ["fa-code", "Build an application", "Plan and build an app step by step.", "Help me plan and build an application step by step. Start by asking what the application should do."],
      ["fa-lightbulb", "Explore an idea", "Turn an idea into a practical plan.", "Help me turn an idea into a practical plan. Ask me the key questions first."],
      ["fa-graduation-cap", "Learn something", "Explain a topic with examples.", "Teach me a topic step by step with beginner-friendly explanations and practical examples."],
      ["fa-list-check", "Organise a project", "Break work into clear tasks.", "Help me organise a project into clear goals, tasks, and milestones."]
    ];
    options.forEach(([iconClass, headingText, detailText, promptText]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chat-suggestion";
      const icon = document.createElement("i");
      icon.className = "fa-solid " + iconClass;
      icon.setAttribute("aria-hidden", "true");
      const heading = document.createElement("strong");
      heading.textContent = headingText;
      const detail = document.createElement("span");
      detail.textContent = detailText;
      button.append(icon, heading, detail);
      button.addEventListener("click", () => {
        promptEl.value = promptText;
        promptEl.focus();
        promptEl.dispatchEvent(new Event("input", { bubbles: true }));
      });
      suggestions.appendChild(button);
    });
    welcome.append(eyebrow, title, description, suggestions);
    messagesEl.appendChild(welcome);
  }

  function clearWelcome() {
    messagesEl.querySelector(".chat-welcome")?.remove();
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
    const attachmentContext = pendingTextAttachments.map((item) =>
      "\\n\\n[Attached text file: " + item.name + "]\\n" + item.content
    ).join("");
    const selectedProject = chatProjectSelect && chatProjectSelect.selectedOptions[0];
    const projectContext = selectedProject && selectedProject.value
      ? "\\n\\n[Selected project context: " + selectedProject.textContent + "]"
      : "";
    const searchPrefix = webSearchToggle && webSearchToggle.checked
      ?  "
      : "";
    const messageForApi = searchPrefix + text + projectContext + attachmentContext;
    clearWelcome();
    renderMessage("user", text + (pendingTextAttachments.length ? "\\n\\nAttached: " + pendingTextAttachments.map((item) => item.name).join(", ") : "") + (selectedProject && selectedProject.value ? "\\nProject: " + selectedProject.textContent : "") + (webSearchToggle && webSearchToggle.checked ? "\\nWeb search requested" : ""));
    sendBtn.disabled = true;
    promptEl.disabled = true;
    setConversationControlsBusy(true);
    renderNotice("Thinking...");

    try {
      const csrfToken = await getCsrfToken();
      const res = await fetch("/api/chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({
          message: messageForApi,
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
      setConversationControlsBusy(false);
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
  if (!conversationId && !prefill) renderWelcome();
  loadHistory();
  loadConversationList();
  loadApprovals();
})();
