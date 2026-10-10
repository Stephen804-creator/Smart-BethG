// Smart BethG - shared topbar icon panels.
(function () {
  function closeAllPanels() {
    document.querySelectorAll(".sbg-panel").forEach((panel) => panel.remove());
    document.querySelectorAll("[data-panel-open]").forEach((el) => (el.dataset.panelOpen = "0"));
  }

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
      document.addEventListener("click", function onDocClick(event) {
        if (!panel.contains(event.target) && event.target !== anchorEl && !anchorEl.contains(event.target)) {
          panel.remove();
          anchorEl.dataset.panelOpen = "0";
          document.removeEventListener("click", onDocClick);
        }
      });
    }, 0);
    return body;
  }

  function showEmpty(body, message) {
    const p = document.createElement("p");
    p.style.cssText = "color:var(--text-secondary); font-size:14px; margin:0;";
    p.textContent = message;
    body.replaceChildren(p);
  }

  function addUsageRow(body, label, value, emphasize) {
    const row = document.createElement("div");
    row.style.cssText = "display:flex; justify-content:space-between; gap:10px; font-size:13px; line-height:1.7;";
    const labelEl = document.createElement("span");
    labelEl.textContent = label;
    const valueEl = document.createElement(emphasize ? "strong" : "span");
    valueEl.textContent = String(value);
    row.append(labelEl, valueEl);
    body.appendChild(row);
  }

  const notifBtn = document.getElementById("notificationsButton");
  if (notifBtn) {
    notifBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      const body = openPanel(notifBtn, "Notifications");
      if (body) showEmpty(body, "No notifications yet.");
    });
  }

  const usageBtn = document.getElementById("usageButton");
  if (usageBtn) {
    usageBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const body = openPanel(usageBtn, "Token usage");
      if (!body) return;
      showEmpty(body, "Loading...");
      try {
        const res = await fetch("/api/chat/usage", { credentials: "same-origin" });
        if (res.status === 401) {
          window.location.href = "/login";
          return;
        }
        if (!res.ok) throw new Error("Usage request failed.");
        const data = await res.json();
        const totals = data.totals || {};
        body.replaceChildren();
        addUsageRow(body, "Input tokens", totals.input_tokens || 0, true);
        addUsageRow(body, "Output tokens", totals.output_tokens || 0, true);
        addUsageRow(body, "Replies", totals.message_count || 0, true);
        const budget = data.budget || {};
        addUsageRow(
          body,
          "Daily tokens reserved",
          String(budget.tokens_reserved_or_used || 0) + " / " + String(budget.daily_token_limit || 0),
          true
        );
        addUsageRow(
          body,
          "Estimated spend today",
          "$" + Number(budget.estimated_spend_usd || 0).toFixed(4) +
            " / $" + Number(budget.daily_spend_limit_usd || 0).toFixed(2),
          true
        );
        addUsageRow(
          body,
          "Provider attempts",
          String(budget.requests || 0) + " / " + String(budget.daily_request_limit || 0),
          false
        );
        (data.by_model || []).forEach((model) => {
          const row = document.createElement("div");
          row.style.cssText = "display:flex; justify-content:space-between; gap:10px; font-size:12px; color:var(--text-secondary); padding:6px 0; border-top:1px solid var(--border);";
          const name = document.createElement("span");
          name.style.overflowWrap = "anywhere";
          name.textContent = String(model.provider || "?") + " / " + String(model.model || "?");
          const count = document.createElement("span");
          count.textContent = String((Number(model.input_tokens) || 0) + (Number(model.output_tokens) || 0)) + " tok";
          row.append(name, count);
          body.appendChild(row);
        });
        if (!(data.by_model || []).length) {
          const empty = document.createElement("p");
          empty.style.cssText = "color:var(--text-secondary); font-size:14px; margin:8px 0 0;";
          empty.textContent = "No usage yet.";
          body.appendChild(empty);
        }
      } catch (err) {
        showEmpty(body, "Couldn't load usage right now.");
      }
    });
  }

  const settingsBtn = document.getElementById("settingsButton");
  if (settingsBtn) {
    settingsBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const body = openPanel(settingsBtn, "Account");
      if (!body) return;
      showEmpty(body, "Loading...");
      try {
        const res = await fetch("/auth/me", { credentials: "same-origin" });
        if (res.status === 401) {
          window.location.href = "/login";
          return;
        }
        if (!res.ok) throw new Error("Account request failed.");
        const user = await res.json();
        const line = document.createElement("div");
        line.style.cssText = "font-size:13px; line-height:1.8; overflow-wrap:anywhere;";
        line.append(document.createTextNode("Signed in as "));
        const username = document.createElement("strong");
        username.textContent = String(user.username || "-");
        line.appendChild(username);
        body.replaceChildren(line);
      } catch (err) {
        showEmpty(body, "Couldn't load account info.");
      }
    });
  }
})();
