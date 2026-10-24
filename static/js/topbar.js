// Smart BethG - shared topbar icon panels.
(function () {
  function closeAllPanels() {
    document.querySelectorAll(".sbg-panel").forEach((panel) => panel.remove());
    document.querySelectorAll("[data-panel-open]").forEach((el) => { el.dataset.panelOpen = "0"; el.setAttribute("aria-expanded", "false"); });
  }

  function openPanel(anchorEl, title) {
    const alreadyOpen = anchorEl.dataset.panelOpen === "1";
    closeAllPanels();
    if (alreadyOpen) return null;
    anchorEl.dataset.panelOpen = "1";
    anchorEl.setAttribute("aria-expanded", "true");

    const panel = document.createElement("div");
    panel.className = "sbg-panel";
    panel.setAttribute("role", "region");
    panel.setAttribute("aria-label", title);

    const heading = document.createElement("div");
    heading.className = "sbg-panel-heading";
    heading.textContent = title;
    panel.appendChild(heading);

    const body = document.createElement("div");
    panel.appendChild(body);
    const container = anchorEl.closest(".topbar-actions") || anchorEl.parentElement;
    container.appendChild(panel);

    function closePanel(restoreFocus = false) {
      panel.remove();
      anchorEl.dataset.panelOpen = "0";
      anchorEl.setAttribute("aria-expanded", "false");
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onDocKeydown);
      if (restoreFocus) anchorEl.focus();
    }

    function onDocClick(event) {
      if (!panel.contains(event.target) && !anchorEl.contains(event.target)) {
        closePanel();
      }
    }

    function onDocKeydown(event) {
      if (event.key === "Escape") closePanel(true);
    }

    setTimeout(() => {
      document.addEventListener("click", onDocClick);
      document.addEventListener("keydown", onDocKeydown);
    }, 0);
    return body;
  }

  function showEmpty(body, message) {
    const p = document.createElement("p");
    p.className = "sbg-panel-empty";
    p.textContent = message;
    body.replaceChildren(p);
  }

  function addUsageRow(body, label, value, emphasize) {
    const row = document.createElement("div");
    row.className = "sbg-usage-row";
    const labelEl = document.createElement("span");
    labelEl.textContent = label;
    const valueEl = document.createElement(emphasize ? "strong" : "span");
    valueEl.textContent = String(value);
    row.append(labelEl, valueEl);
    body.appendChild(row);
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
          row.className = "sbg-usage-row sbg-usage-model";
          const name = document.createElement("span");
          name.className = "sbg-usage-model-name";
          name.textContent = String(model.provider || "?") + " / " + String(model.model || "?");
          const count = document.createElement("span");
          count.textContent = String((Number(model.input_tokens) || 0) + (Number(model.output_tokens) || 0)) + " tok";
          row.append(name, count);
          body.appendChild(row);
        });
        if (!(data.by_model || []).length) {
          const empty = document.createElement("p");
          empty.className = "sbg-panel-empty sbg-panel-empty-spaced";
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
        line.className = "sbg-account-line";
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
