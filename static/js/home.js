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
  const attachedFilesEl = document.getElementById("attachedFiles");
  const attachmentStatus = document.getElementById("attachmentStatus");
  const filePickers = {
    Files: document.getElementById("filePicker"),
    Photos: document.getElementById("photoPicker"),
    Camera: document.getElementById("cameraPicker"),
    Folders: document.getElementById("folderPicker"),
  };
  let selectedFiles = [];
  window.sbgSelectedFiles = selectedFiles;
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
    attachmentButton.disabled = temporaryChat;
    if (temporaryChat && selectedFiles.length) {
      clearSelectedFiles();
      showAttachmentStatus("Attachments are not included in Temporary Chat. Uploaded files remain in your library.");
    }
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

  function showAttachmentStatus(message) {
    attachmentStatus.textContent = message;
    attachmentStatus.hidden = !message;
  }
  function renderAttachedFiles() {
    attachedFilesEl.replaceChildren();
    attachedFilesEl.hidden = selectedFiles.length === 0;
    selectedFiles.forEach((file, index) => {
      const chip = document.createElement("span"); chip.className = "attached-file-chip";
      const icon = document.createElement("i"); icon.className = "fa-regular fa-file";
      const name = document.createElement("span"); name.textContent = file.filename;
      const remove = document.createElement("button"); remove.type = "button"; remove.setAttribute("aria-label", "Remove " + file.filename); remove.innerHTML = '<i class="fa-solid fa-xmark"></i>';
      remove.addEventListener("click", () => { selectedFiles.splice(index, 1); window.sbgSelectedFiles = selectedFiles; renderAttachedFiles(); });
      chip.append(icon, name, remove); attachedFilesEl.appendChild(chip);
    });
    window.sbgSelectedFiles = selectedFiles;
  }
  function clearSelectedFiles() {
    selectedFiles = [];
    window.sbgSelectedFiles = selectedFiles;
    renderAttachedFiles();
  }
  document.addEventListener("sbg:files-clear", clearSelectedFiles);

  async function uploadSelectedFiles(fileList) {
    if (temporaryChat) { showAttachmentStatus("File attachments are disabled in Temporary Chat."); return; }
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const remaining = Math.max(0, 10 - selectedFiles.length);
    if (files.length > remaining) showAttachmentStatus("You can attach up to 10 files per message. Uploading the first " + remaining + ".");
    const batch = files.slice(0, remaining);
    attachmentButton.disabled = true;
    let added = 0;
    try {
      for (let index = 0; index < batch.length; index += 1) {
        const file = batch[index];
        showAttachmentStatus("Uploading " + (index + 1) + " of " + batch.length + "…");
        const csrfResponse = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
        if (!csrfResponse.ok) throw new Error("Could not obtain security token.");
        const csrf = await csrfResponse.json();
        const formData = new FormData(); formData.append("file", file, file.name);
        const response = await fetch("/api/v1/files", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf.csrf_token }, body: formData });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) { window.location.href = "/login"; return; }
        if (!response.ok) throw new Error(data.detail || "Could not upload " + file.name + ".");
        selectedFiles.push({ id: data.id, filename: data.filename || file.name, content_type: data.content_type || file.type });
        added += 1; renderAttachedFiles();
      }
      showAttachmentStatus(added + " file" + (added === 1 ? "" : "s") + " attached. Uploaded files are also saved in your library.");
    } catch (error) {
      showAttachmentStatus(error.message);
    } finally {
      attachmentButton.disabled = temporaryChat;
      Object.values(filePickers).forEach((picker) => { picker.value = ""; });
    }
  }

  attachmentButton.addEventListener("click", () => {
    if (temporaryChat) { showAttachmentStatus("File attachments are disabled in Temporary Chat."); return; }
    attachmentPopover.hidden = !attachmentPopover.hidden;
  });
  attachmentPopover.querySelectorAll("[data-attach]").forEach((button) => {
    button.addEventListener("click", () => {
      const picker = filePickers[button.dataset.attach];
      attachmentPopover.hidden = true;
      if (picker) picker.click();
    });
  });
  Object.values(filePickers).forEach((picker) => picker.addEventListener("change", () => uploadSelectedFiles(picker.files)));

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
