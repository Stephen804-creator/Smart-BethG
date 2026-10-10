// Smart BethG - shared topbar icon panels (notifications, usage, settings).
// Every number/state shown here comes from a real endpoint - no
// placeholder counts or fabricated activity.
(function () {
  function closeAllPanels() {
    document.querySelectorAll(".sbg-panel").forEach((p) => p.remove());
    document.querySelectorAll("[data-panel-open]").forEach((el) => (el.dataset.panelOpen = "0"));
  }

  // Opens (or closes, if already open) a panel anchored under anchorEl.
  // Returns the panel's body element to fill in asynchronously, or null
  // if the panel was closed instead of opened.
  function openPanel(anchorEl, title) {
    const alreadyOpen = anchorEl.dataset.panelOpen === "1";
    closeAllPanels();
    if (alreadyOpen) return null;

    anchorEl.dataset.panelOpen = "1";

    const panel = document.createElement("div");
    panel.className = "sbg-panel";
    panel.style.cssText =
      "position:absolute; top:52px; right:0; width:280px; max-width:88vw; " +
      "background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-md, 12px); " +
      "box-shadow:0 12px 32px rgba(0,0,0,0.4); padding:16px; z-index:50; color:var(--text-primary);";

    const heading = document.createElement("div");
    heading.style.cssText = "font-weight:700; margin-bottom:10px; font-size:14px;";
    heading.textContent = title;
    panel.appendChild(heading);

    const body = document.createElement("div");
    panel.appendChild(body);

    const container = anchorEl.closest(".topbar-actions") || anchorEl.parentElement;
    container.style.position = container.style.position || "relative";
    container.appendChild(panel);

    setTimeout(() => {
      document.addEventListener("click", function onDocClick(e) {
        if (!panel.contains(e.target) && e.target !== anchorEl && !anchorEl.contains(e.target)) {
          panel.remove();
          anchorEl.dataset.panelOpen = "0";
          document.removeEventListener("click", onDocClick);
        }
      });
    }, 0);

    return body;
  }

  const emptyState = (text) =>
    `<p style="color:var(--text-secondary); font-size:14px; margin:0;">${text}</p>`;

  // --- Notifications: honestly empty until something real generates one ---
  const notifBtn = document.getElementById("notificationsButton");
  if (notifBtn) {
    notifBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const body = openPanel(notifBtn, "Notifications");
      if (body) body.innerHTML = emptyState("No notifications yet.");
    });
  }

  // --- Usage: real token totals from /api/chat/usage ---
  const usageBtn = document.getElementById("usageButton");
  if (usageBtn) {
    usageBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const body = openPanel(usageBtn, "Token usage");
      if (!body) return;
      body.innerHTML = emptyState("Loading...");
      try {
        const res = await fetch("/api/chat/usage", { credentials: "same-origin" });
        if (res.status === 401) {
          window.location.href = "/login";
          return;
        }
        const data = await res.json();
        const t = data.totals || { input_tokens: 0, output_tokens: 0, message_count: 0 };
        const rows = (data.by_model || [])
          .map(
            (m) =>
              `<div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-secondary); padding:4px 0; border-top:1px solid var(--border);">
                 <span>${m.provider || "?"} / ${m.model || "?"}</span>
                 <span>${(m.input_tokens || 0) + (m.output_tokens || 0)} tok</span>
               </div>`
          )
          .join("");
        body.innerHTML =
          `<div style="font-size:13px; line-height:1.7;">
             <div>Input tokens: <strong>${t.input_tokens}</strong></div>
             <div>Output tokens: <strong>${t.output_tokens}</strong></div>
             <div>Replies: <strong>${t.message_count}</strong></div>
           </div>` + (rows || emptyState("No usage yet."));
      } catch (err) {
        body.innerHTML = emptyState("Couldn't load usage right now.");
      }
    });
  }

  // --- Settings: real account info, no fake toggles ---
  const settingsBtn = document.getElementById("settingsButton");
  if (settingsBtn) {
    settingsBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const body = openPanel(settingsBtn, "Account");
      if (!body) return;
      body.innerHTML = emptyState("Loading...");
      try {
        const res = await fetch("/auth/me", { credentials: "same-origin" });
        if (res.status === 401) {
          window.location.href = "/login";
          return;
        }
        const user = await res.json();
        body.innerHTML = `<div style="font-size:13px; line-height:1.8;">Signed in as <strong>${user.username || "-"}</strong></div>`;
      } catch (err) {
        body.innerHTML = emptyState("Couldn't load account info.");
      }
    });
  }
})();
