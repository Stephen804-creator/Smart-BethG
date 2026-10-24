// Smart BethG - shared topbar icon panels.
(function () {
  let activePanelClose = null;

  function closeAllPanels() {
    if (activePanelClose) {
      activePanelClose(false);
      return;
    }
    document.querySelectorAll(".sbg-panel").forEach((panel) => panel.remove());
    document.querySelectorAll("[data-panel-open]").forEach((el) => {
      el.dataset.panelOpen = "0";
      el.setAttribute("aria-expanded", "false");
    });
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
      if (activePanelClose === closePanel) activePanelClose = null;
      if (restoreFocus) anchorEl.focus();
    }

    activePanelClose = closePanel;

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
        const section = document.createElement("div");
        section.className = "sbg-panel-section";
        const sectionTitle = document.createElement("p");
        sectionTitle.className = "sbg-panel-section-title";
        sectionTitle.textContent = "Quick access";
        section.appendChild(sectionTitle);
        const helpAction = document.createElement("button");
        helpAction.type = "button";
        helpAction.className = "sbg-panel-action";
        const makePanelAction = (iconClass, headingText, detailText, onClick) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "sbg-panel-action";
          const icon = document.createElement("i");
          icon.className = iconClass;
          icon.setAttribute("aria-hidden", "true");
          const copy = document.createElement("span");
          const heading = document.createElement("strong");
          heading.textContent = headingText;
          const detail = document.createElement("small");
          detail.textContent = detailText;
          copy.append(heading, detail);
          const chevron = document.createElement("i");
          chevron.className = "fa-solid fa-chevron-right sbg-panel-action-chevron";
          chevron.setAttribute("aria-hidden", "true");
          button.append(icon, copy, chevron);
          button.addEventListener("click", onClick);
          return button;
        };
        const helpAction = makePanelAction(
          "fa-solid fa-circle-question",
          "Getting started",
          "Open the product tour",
          () => {
            closeAllPanels();
            document.getElementById("helpButton")?.click();
          }
        );
        const usageAction = makePanelAction(
          "fa-solid fa-chart-simple",
          "Usage overview",
          "Review your current usage",
          () => {
            closeAllPanels();
            document.getElementById("usageButton")?.click();
          }
        );
        section.append(helpAction, usageAction);
        // Display preferences are local to this browser for now; they do not claim to change server-side account settings.
        const preferences = document.createElement("section");
        preferences.className = "sbg-preferences";
        preferences.setAttribute("aria-label", "Display preferences");
        const preferencesTitle = document.createElement("p");
        preferencesTitle.className = "sbg-preferences-title";
        preferencesTitle.textContent = "Display & accessibility";
        preferences.appendChild(preferencesTitle);

        const readPreference = (key, fallback) => {
          try { return localStorage.getItem("sbg:preference:" + key) || fallback; }
          catch (_) { return fallback; }
        };
        const savePreference = (key, value) => {
          try { localStorage.setItem("sbg:preference:" + key, value); } catch (_) {}
        };
        const applyPreference = (key, value) => {
          if (key === "theme") document.documentElement.dataset.theme = value;
          if (key === "font-size") document.documentElement.dataset.fontSize = value;
          if (key === "font-style") document.documentElement.dataset.fontStyle = value;
          savePreference(key, value);
        };
        const field = (labelText, helpText) => {
          const wrapper = document.createElement("div");
          wrapper.className = "sbg-preference-field";
          const label = document.createElement("div");
          label.className = "sbg-preference-label";
          label.textContent = labelText;
          wrapper.appendChild(label);
          if (helpText) {
            const help = document.createElement("small");
            help.className = "sbg-preference-help";
            help.textContent = helpText;
            wrapper.appendChild(help);
          }
          return wrapper;
        };
        const choiceGroup = (key, choices, columnsClass) => {
          const group = document.createElement("div");
          group.className = "sbg-choice-group" + (columnsClass ? " " + columnsClass : "");
          group.setAttribute("role", "group");
          const selected = readPreference(key, key === "theme" ? "dark" : key === "font-size" ? "default" : "standard");
          choices.forEach(([value, label]) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "sbg-choice";
            button.textContent = label;
            button.setAttribute("aria-pressed", String(selected === value));
            button.addEventListener("click", () => {
              applyPreference(key, value);
              group.querySelectorAll("button").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
            });
            group.appendChild(button);
          });
          applyPreference(key, selected);
          return group;
        };

        const themeField = field("Theme", "Choose the appearance used by Smart BethG.");
        themeField.appendChild(choiceGroup("theme", [["light", "Light"], ["dark", "Dark"]]));
        preferences.appendChild(themeField);

        const sizeField = field("Font size", "Adjust text size across the workspace.");
        sizeField.appendChild(choiceGroup("font-size", [["small", "Small"], ["default", "Default"], ["large", "Large"]], "three"));
        preferences.appendChild(sizeField);

        const styleField = field("Font style", "Choose a comfortable reading style.");
        styleField.appendChild(choiceGroup("font-style", [["standard", "Standard"], ["serif", "Serif"]]));
        preferences.appendChild(styleField);

        body.replaceChildren(line, section, preferences);
      } catch (err) {
        showEmpty(body, "Couldn't load account info.");
      }
    });
  }
})();
