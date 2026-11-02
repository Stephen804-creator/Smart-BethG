(function () {
  const drawer = document.getElementById("homeDrawer");
  const scrim = document.getElementById("homeScrim");
  const menuButton = document.getElementById("menuButton");
  const closeDrawerButton = document.getElementById("closeDrawerButton");
  const avatarButton = document.getElementById("avatarButton");
  const avatarPopover = document.getElementById("avatarPopover");
  const modeButton = document.getElementById("modeButton");
  const modeSheet = document.getElementById("modeSheet");
  const sheetBackdrop = document.getElementById("sheetBackdrop");
  const prompt = document.getElementById("prompt");
  const welcomePanel = document.getElementById("welcomePanel");
  const conversationPanel = document.getElementById("conversationPanel");
  const taskGrid = document.getElementById("taskGrid");
  const temporaryButton = document.getElementById("temporaryChatButton");
  const temporaryBanner = document.getElementById("temporaryBanner");
  const composerSurface = document.getElementById("composerSurface");
  const attachmentButton = document.getElementById("attachmentButton");
  const attachmentPopover = document.getElementById("attachmentPopover");
  let currentMode = "Balanced";
  window.sbgCurrentMode = currentMode;
  function announceMode() {
    window.sbgCurrentMode = currentMode;
    document.dispatchEvent(new CustomEvent("sbg:mode-change", { detail: { mode: currentMode } }));
  }
  let temporaryChat = false;
  window.sbgTemporaryChat = false;
  function announceTemporaryMode() {
    window.sbgTemporaryChat = temporaryChat;
    document.dispatchEvent(new CustomEvent("sbg:temporary-chat", { detail: { active: temporaryChat } }));
  }

  function setDrawer(open) {
    drawer.classList.toggle("is-open", open);
    scrim.hidden = !open;
    drawer.setAttribute("aria-hidden", String(!open));
    menuButton.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("drawer-open", open);
    if (open) closeDrawerButton.focus();
    else menuButton.focus();
  }
  menuButton.addEventListener("click", () => setDrawer(true));
  closeDrawerButton.addEventListener("click", () => setDrawer(false));
  scrim.addEventListener("click", () => setDrawer(false));

  document.querySelectorAll("[data-disclosure]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.disclosure;
      const content = document.querySelector('[data-disclosure-content="' + key + '"]');
      const open = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(open));
      content.hidden = !open;
      button.closest(".drawer-group").classList.toggle("is-open", open);
    });
  });

  avatarButton.addEventListener("click", () => {
    const open = avatarPopover.hidden;
    avatarPopover.hidden = !open;
    avatarButton.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (event) => {
    if (!avatarPopover.contains(event.target) && !avatarButton.contains(event.target)) {
      avatarPopover.hidden = true;
      avatarButton.setAttribute("aria-expanded", "false");
    }
    if (!attachmentPopover.contains(event.target) && !attachmentButton.contains(event.target)) {
      attachmentPopover.hidden = true;
    }
  });

  const logoutButton = document.getElementById("logoutButton");
  logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    try {
      const csrfResponse = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
      if (!csrfResponse.ok) throw new Error("CSRF unavailable");
      const csrf = await csrfResponse.json();
      const response = await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": csrf.csrf_token },
      });
      if (!response.ok) throw new Error("Logout failed");
      window.location.href = "/login";
    } catch (error) {
      logoutButton.disabled = false;
      logoutButton.title = "Could not sign out. Please retry.";
    }
  });

  function openModeSheet(open) {
    modeSheet.hidden = !open;
    sheetBackdrop.hidden = !open;
    modeButton.setAttribute("aria-expanded", String(open));
    if (open) modeSheet.querySelector('[data-mode="' + currentMode + '"]').focus();
    else modeButton.focus();
  }
  modeButton.addEventListener("click", () => openModeSheet(modeSheet.hidden));
  sheetBackdrop.addEventListener("click", () => openModeSheet(false));
  modeSheet.querySelectorAll("[data-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      currentMode = button.dataset.mode;
      document.getElementById("modeLabel").textContent = currentMode;
      announceMode();
      modeSheet.querySelectorAll("[data-mode]").forEach((item) => {
        const selected = item === button;
        item.classList.toggle("is-selected", selected);
        item.querySelector(".mode-check").innerHTML = selected ? '<i class="fa-solid fa-check"></i>' : "";
      });
      openModeSheet(false);
    });
  });

  taskGrid.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      prompt.value = button.dataset.prompt + " ";
      prompt.focus();
      prompt.setSelectionRange(prompt.value.length, prompt.value.length);
    });
  });

  temporaryButton.addEventListener("click", () => {
    temporaryChat = !temporaryChat;
    temporaryBanner.hidden = !temporaryChat;
    composerSurface.classList.toggle("is-temporary", temporaryChat);
    temporaryButton.classList.toggle("is-active", temporaryChat);
    temporaryButton.setAttribute("aria-pressed", String(temporaryChat));
    temporaryButton.setAttribute("aria-label", temporaryChat ? "Temporary chat is on" : "Start temporary chat");
    announceTemporaryMode();
  });
  document.getElementById("endTemporaryChat").addEventListener("click", () => {
    temporaryChat = false;
    temporaryBanner.hidden = true;
    composerSurface.classList.remove("is-temporary");
    temporaryButton.classList.remove("is-active");
    temporaryButton.setAttribute("aria-pressed", "false");
    temporaryButton.setAttribute("aria-label", "Start temporary chat");
    announceTemporaryMode();
  });

  attachmentButton.addEventListener("click", () => {
    attachmentPopover.hidden = !attachmentPopover.hidden;
  });
  attachmentPopover.querySelectorAll("[data-attach]").forEach((button) => {
    button.addEventListener("click", () => {
      const feature = button.dataset.attach;
      attachmentPopover.hidden = true;
      const notice = document.createElement("p");
      notice.className = "composer-feature-notice";
      notice.textContent = feature + " attachment is not connected in this version yet.";
      document.querySelector(".home-composer-wrap").appendChild(notice);
      window.setTimeout(() => notice.remove(), 4500);
    });
  });

  const micButton = document.getElementById("micButton");
  micButton.addEventListener("click", () => {
    micButton.title = "Voice input is not connected in this version yet.";
    micButton.setAttribute("aria-label", "Voice input is not connected yet");
  });

  const messages = document.getElementById("messages");
  const observer = new MutationObserver(() => {
    const hasMessages = messages.children.length > 0;
    welcomePanel.hidden = hasMessages;
    conversationPanel.hidden = !hasMessages;
    document.body.classList.toggle("has-conversation", hasMessages);
  });
  observer.observe(messages, { childList: true });

  const creditsButton = document.getElementById("creditsButton");
  creditsButton.addEventListener("click", () => {
    window.location.href = "/workspace/credits";
  });

  async function loadCreditBudget() {
    const label = document.getElementById("creditsLabel");
    try {
      const response = await fetch("/api/v1/chat/usage", { credentials: "same-origin", cache: "no-store" });
      if (response.status === 401) { window.location.href = "/login"; return; }
      if (!response.ok) return;
      const data = await response.json();
      const budget = data.budget || {};
      const limit = Number(budget.daily_token_limit || 0);
      const used = Number(budget.tokens_reserved_or_used || 0);
      if (limit > 0) label.textContent = Math.max(0, limit - used).toLocaleString() + " tokens left";
    } catch (_) { /* Keep the neutral chip label if usage is unavailable. */ }
  }
  loadCreditBudget();

  const params = new URLSearchParams(window.location.search);
  if (params.has("prompt")) {
    prompt.value = params.get("prompt") || "";
    prompt.focus();
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (drawer.classList.contains("is-open")) setDrawer(false);
      if (!modeSheet.hidden) openModeSheet(false);
      avatarPopover.hidden = true;
      attachmentPopover.hidden = true;
    }
  });
})();
