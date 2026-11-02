(function () {
  const active = document.getElementById("activeMissions");
  const done = document.getElementById("doneMissions");
  const status = document.getElementById("missionPageStatus");
  function card(mission) {
    const item = document.createElement("article");
    item.className = "mission-card";
    const title = document.createElement("h2");
    title.textContent = mission.objective || "Untitled mission";
    const meta = document.createElement("p");
    meta.className = "mission-card-meta";
    const state = String(mission.status || "pending").replaceAll("_", " ");
    meta.textContent = state.charAt(0).toUpperCase() + state.slice(1);
    const progress = document.createElement("div");
    progress.className = "mission-progress";
    progress.setAttribute("role", "progressbar");
    progress.setAttribute("aria-label", "Mission status progress");
    progress.setAttribute("aria-valuemin", "0");
    progress.setAttribute("aria-valuemax", "100");
    const value = mission.status === "completed" ? 100 : 0;
    if (["running", "awaiting_approval"].includes(mission.status)) {
      progress.setAttribute("aria-label", "Mission is active; detailed progress is not available.");
    } else {
      progress.setAttribute("aria-valuenow", String(value));
    }
    const fill = document.createElement("span");
    if (["running", "awaiting_approval"].includes(mission.status)) fill.className = "is-indeterminate";
    else fill.style.width = value + "%";
    progress.appendChild(fill);
    item.append(title, meta, progress);
    return item;
  }
  async function load() {
    try {
      const response = await fetch("/api/v1/missions", { credentials: "same-origin", cache: "no-store" });
      if (response.status === 401) { window.location.href = "/login"; return; }
      if (!response.ok) throw new Error("Could not load missions.");
      const data = await response.json();
      const missions = Array.isArray(data.missions) ? data.missions : [];
      active.replaceChildren();
      done.replaceChildren();
      const activeItems = missions.filter((m) => !["completed", "cancelled"].includes(m.status));
      const doneItems = missions.filter((m) => ["completed", "cancelled"].includes(m.status));
      activeItems.forEach((m) => active.appendChild(card(m)));
      doneItems.forEach((m) => done.appendChild(card(m)));
      if (!activeItems.length) active.innerHTML = '<p class="subpage-empty">No active missions yet.</p>';
      if (!doneItems.length) done.innerHTML = '<p class="subpage-empty">Completed missions will appear here.</p>';
      status.textContent = "";
    } catch (error) {
      active.replaceChildren();
      active.innerHTML = '<p class="subpage-error">Missions could not be loaded. Refresh to try again.</p>';
      status.textContent = "";
    }
  }
  load();
})();