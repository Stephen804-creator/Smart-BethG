(function () {
  const form = document.getElementById("campaignForm");
  const campaignList = document.getElementById("campaignList");
  const campaignStatus = document.getElementById("campaignListStatus");
  const formStatus = document.getElementById("campaignFormStatus");
  const connectorList = document.getElementById("connectorList");
  const connectedAccounts = document.getElementById("connectedAccounts");
  const autonomyMode = document.getElementById("autonomyMode");
  const consentRow = document.getElementById("autoPublishConsent");
  if (!form || !campaignList) return;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  async function csrfToken() {
    const response = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error("Could not obtain a security token. Refresh and sign in again.");
    const data = await response.json();
    if (!data.csrf_token) throw new Error("Security token is missing.");
    return data.csrf_token;
  }

  async function api(path, options = {}) {
    const headers = Object.assign({ "Accept": "application/json" }, options.headers || {});
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (options.method && !["GET", "HEAD", "OPTIONS"].includes(options.method.toUpperCase())) {
      headers["X-CSRF-Token"] = await csrfToken();
    }
    const response = await fetch(path, Object.assign({
      credentials: "same-origin",
      cache: "no-store",
      headers,
    }, options, { headers }));
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Your session expired. Sign in again.");
    }
    if (!response.ok) {
      const message = data.detail || data.error?.message || data.message || "Request failed.";
      throw new Error(String(message));
    }
    return data;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function statusPill(status) {
    const pill = element("span", "status-pill", String(status || "unknown").replaceAll("_", " "));
    pill.dataset.status = status || "unknown";
    return pill;
  }

  function selectedPlatforms() {
    return $$('input[name="platforms"]:checked', form).map(input => input.value);
  }

  function localDateTimeToUtc(value, timeZone) {
    if (!value) return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
    if (!match) throw new Error("Enter a valid date and time.");
    const parts = match.slice(1).map(Number);
    const targetWall = Date.UTC(parts[0], parts[1] - 1, parts[2], parts[3], parts[4]);
    let guess = targetWall;
    const formatter = new Intl.DateTimeFormat("en-GB", {
      timeZone, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    });
    for (let i = 0; i < 4; i += 1) {
      const mapped = {};
      formatter.formatToParts(new Date(guess)).forEach(part => {
        if (part.type !== "literal") mapped[part.type] = Number(part.value);
      });
      const observedWall = Date.UTC(mapped.year, mapped.month - 1, mapped.day, mapped.hour, mapped.minute);
      guess += targetWall - observedWall;
    }
    const check = {};
    formatter.formatToParts(new Date(guess)).forEach(part => {
      if (part.type !== "literal") check[part.type] = Number(part.value);
    });
    if (check.year !== parts[0] || check.month !== parts[1] || check.day !== parts[2] ||
        check.hour !== parts[3] || check.minute !== parts[4]) {
      throw new Error("That local time does not exist in the selected timezone because of a clock change.");
    }
    return new Date(guess).toISOString();
  }

  function renderConnectors(connectors) {
    connectorList.replaceChildren();
    connectors.forEach(connector => {
      const card = element("article", "connector-card");
      const heading = element("div");
      heading.style.cssText = "display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;";
      heading.append(element("h3", "", connector.display_name), statusPill(connector.status));
      card.append(heading, element("p", "muted", connector.setup_notes));
      connectorList.append(card);
    });
    if (!connectors.length) connectorList.append(element("p", "empty-state", "No connector information is available."));
  }

  function renderAccounts(accounts) {
    connectedAccounts.replaceChildren();
    if (!accounts.length) {
      connectedAccounts.append(element("p", "empty-state", "No social accounts are connected yet. Official OAuth connection flows are the next integration milestone."));
      return;
    }
    accounts.forEach(account => {
      const card = element("article", "connector-card");
      card.append(element("h3", "", account.display_name || account.external_account_id));
      card.append(element("p", "muted", account.platform + " · " + account.status));
      connectedAccounts.append(card);
    });
  }

  async function loadConnectors() {
    connectorList.replaceChildren(element("p", "muted", "Loading connector status…"));
    connectedAccounts.replaceChildren(element("p", "muted", "Loading connected accounts…"));
    try {
      const [catalog, accounts] = await Promise.all([
        api("/connectors"),
        api("/connectors/social-accounts"),
      ]);
      renderConnectors(catalog.connectors || []);
      renderAccounts(accounts.accounts || []);
    } catch (error) {
      connectorList.replaceChildren(element("p", "status-message", error.message));
      connectedAccounts.replaceChildren(element("p", "status-message", error.message));
    }
  }

  function renderCampaign(campaign) {
    const card = element("article", "campaign-card");
    const top = element("div");
    top.style.cssText = "display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;";
    const titleGroup = element("div");
    titleGroup.append(element("h3", "", campaign.name), element("p", "muted", campaign.objective));
    top.append(titleGroup, statusPill(campaign.status));
    card.append(top);

    const meta = element("p", "muted",
      (campaign.platforms || []).join(", ") + " · " + campaign.timezone +
      " · " + campaign.daily_post_limit + " post(s)/day maximum");
    card.append(meta);

    const actions = element("div", "campaign-actions");
    const generate = element("button", "btn", "Generate 30 posts");
    generate.type = "button";
    generate.addEventListener("click", async () => {
      generate.disabled = true;
      campaignStatus.textContent = "Generating campaign content in budget-limited batches…";
      try {
        await api("/social-campaigns/" + campaign.id + "/generate-plan", {
          method: "POST", body: JSON.stringify({ count: 30 }),
        });
        campaignStatus.textContent = "The plan was generated and saved. It has not been published.";
        await loadCampaigns();
      } catch (error) {
        campaignStatus.textContent = error.message;
      } finally { generate.disabled = false; }
    });
    actions.append(generate);

    const statusAction = campaign.status === "active" ? "paused" :
      (campaign.status === "paused" ? "active" : "active");
    if (["planned", "paused", "active"].includes(campaign.status)) {
      const toggle = element("button", "btn", campaign.status === "active" ? "Pause" :
        (campaign.status === "paused" ? "Resume" : "Activate"));
      toggle.type = "button";
      toggle.addEventListener("click", async () => {
        toggle.disabled = true;
        try {
          await api("/social-campaigns/" + campaign.id + "/status", {
            method: "POST", body: JSON.stringify({ status: statusAction }),
          });
          campaignStatus.textContent = "Campaign status updated.";
          await loadCampaigns();
        } catch (error) {
          campaignStatus.textContent = error.message;
        } finally { toggle.disabled = false; }
      });
      actions.append(toggle);
    }
    if (!["cancelled", "completed"].includes(campaign.status)) {
      const cancel = element("button", "btn", "Cancel campaign");
      cancel.type = "button";
      cancel.addEventListener("click", async () => {
        if (!window.confirm("Cancel this campaign and its pending publication jobs?")) return;
        try {
          await api("/social-campaigns/" + campaign.id + "/status", {
            method: "POST", body: JSON.stringify({ status: "cancelled" }),
          });
          campaignStatus.textContent = "Campaign cancelled.";
          await loadCampaigns();
        } catch (error) { campaignStatus.textContent = error.message; }
      });
      actions.append(cancel);
    }
    card.append(actions);

    const posts = element("div", "campaign-posts");
    if (!(campaign.posts || []).length) {
      posts.append(element("p", "empty-state", "No posts yet. Generate a plan to build the campaign calendar."));
    } else {
      campaign.posts.forEach(post => {
        const postCard = element("article", "post-card");
        const heading = element("div");
        heading.style.cssText = "display:flex;justify-content:space-between;gap:8px;align-items:flex-start;flex-wrap:wrap;";
        heading.append(element("h4", "", post.title), statusPill(post.publish_status || post.status));
        postCard.append(heading);
        postCard.append(element("p", "muted", post.platform + " · " +
          (post.scheduled_at ? new Date(post.scheduled_at).toLocaleString() : "Not scheduled")));
        postCard.append(element("p", "post-content", post.content));
        let tags = [];
        try { tags = JSON.parse(post.hashtags || "[]"); } catch (_) {}
        if (tags.length) postCard.append(element("p", "post-hashtags", tags.map(tag => "#" + tag).join(" ")));
        if (post.publish_error_message) postCard.append(element("p", "status-message", post.publish_error_message));
        if (post.status === "draft" || post.status === "in_review") {
          const approve = element("button", "btn", "Approve this post");
          approve.type = "button";
          approve.addEventListener("click", async () => {
            approve.disabled = true;
            try {
              await api("/social-campaigns/" + campaign.id + "/posts/" + post.id + "/approve", { method: "POST" });
              campaignStatus.textContent = "Approval saved. Publishing remains blocked until this platform is connected and its adapter is ready.";
              await loadCampaigns();
            } catch (error) {
              campaignStatus.textContent = error.message;
            } finally { approve.disabled = false; }
          });
          postCard.append(approve);
        }
        posts.append(postCard);
      });
    }
    card.append(posts);
    return card;
  }

  async function loadCampaigns() {
    campaignList.replaceChildren(element("p", "muted", "Loading campaigns…"));
    try {
      const data = await api("/social-campaigns");
      const campaigns = data.campaigns || [];
      const full = await Promise.all(campaigns.map(campaign =>
        api("/social-campaigns/" + campaign.id).catch(() => campaign)
      ));
      campaignList.replaceChildren();
      if (!full.length) {
        campaignList.append(element("p", "empty-state", "No campaigns yet. Create one above to start planning."));
      } else {
        full.forEach(campaign => campaignList.append(renderCampaign(campaign)));
      }
      campaignStatus.textContent = full.length + " campaign(s).";
    } catch (error) {
      campaignList.replaceChildren(element("p", "status-message", error.message));
      campaignStatus.textContent = "Could not load campaigns.";
    }
  }

  autonomyMode.addEventListener("change", () => {
    consentRow.hidden = autonomyMode.value !== "auto_publish_after_campaign_approval";
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    formStatus.textContent = "";
    const button = $("#createCampaignButton");
    button.disabled = true;
    try {
      const values = new FormData(form);
      const platforms = selectedPlatforms();
      if (!platforms.length) throw new Error("Select at least one target platform.");
      const timezone = String(values.get("timezone") || "").trim();
      const startAt = localDateTimeToUtc(String(values.get("start_at") || ""), timezone);
      const endInput = String(values.get("end_at") || "");
      const endAt = endInput ? localDateTimeToUtc(endInput, timezone) : null;
      const mode = String(values.get("autonomy_mode"));
      const autoAuthorized = mode === "auto_publish_after_campaign_approval" &&
        Boolean($('input[name="auto_publish_authorized"]', form).checked);
      if (mode === "auto_publish_after_campaign_approval" && !autoAuthorized) {
        throw new Error("Confirm the exact campaign authority before enabling autonomous publishing.");
      }
      const refs = String(values.get("reference_urls") || "").split(/\r?\n/).map(s => s.trim()).filter(Boolean);
      const payload = {
        name: String(values.get("name")).trim(),
        objective: String(values.get("objective")).trim(),
        audience: String(values.get("audience") || "").trim(),
        tone: String(values.get("tone") || "").trim(),
        reference_urls: refs,
        content_rules: String(values.get("content_rules") || "").trim(),
        platforms,
        timezone,
        start_at: startAt,
        end_at: endAt,
        cadence: {
          interval_days: Number(values.get("interval_days")),
          local_time: String(values.get("local_time")),
        },
        daily_post_limit: Number(values.get("daily_post_limit")),
        autonomy_mode: mode,
        auto_publish_authorized: autoAuthorized,
      };
      const created = await api("/social-campaigns", { method: "POST", body: JSON.stringify(payload) });
      formStatus.textContent = "Campaign created.";
      if (values.get("generate_now")) {
        formStatus.textContent = "Campaign created. Generating posts within your configured usage budget…";
        try {
          await api("/social-campaigns/" + created.id + "/generate-plan", {
            method: "POST", body: JSON.stringify({ count: 30 }),
          });
          formStatus.textContent = "Campaign created and its 30-post plan was saved. Nothing has been published.";
        } catch (error) {
          formStatus.textContent = "Campaign saved, but plan generation did not complete: " + error.message;
        }
      }
      await loadCampaigns();
    } catch (error) {
      formStatus.textContent = error.message;
    } finally { button.disabled = false; }
  });

  $("#refreshConnectors").addEventListener("click", loadConnectors);
  $("#refreshCampaigns").addEventListener("click", loadCampaigns);

  const now = new Date();
  now.setDate(now.getDate() + 1);
  now.setHours(9, 0, 0, 0);
  const toLocalInput = date => {
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 16);
  };
  $('input[name="start_at"]', form).value = toLocalInput(now);
  const end = new Date(now);
  end.setDate(end.getDate() + 30);
  end.setHours(23, 0, 0, 0);
  $('input[name="end_at"]', form).value = toLocalInput(end);

  loadConnectors();
  loadCampaigns();
})();
