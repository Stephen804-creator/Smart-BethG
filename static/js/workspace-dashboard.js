// Smart BethG workspace dashboard: project management and mission tracking.
(function () {
  const projectForm = document.getElementById("projectCreateForm");
  const missionForm = document.getElementById("missionCreateForm");
  if (!projectForm || !missionForm) return;

  const projectList = document.getElementById("projectList");
  const missionList = document.getElementById("missionList");
  const missionProject = document.getElementById("missionProject");
  const dashboardStatus = document.getElementById("workspaceDashboardStatus");
  let csrfToken = null;
  let projects = [];

  async function getCsrfToken() {
    if (csrfToken) return csrfToken;
    const response = await fetch("/auth/csrf", {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Could not obtain a security token. Refresh the page.");
    const data = await response.json();
    csrfToken = data.csrf_token;
    return csrfToken;
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.method && options.method !== "GET") {
      headers.set("X-CSRF-Token", await getCsrfToken());
    }
    if (options.body) headers.set("Content-Type", "application/json");
    const response = await fetch(path, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Please sign in again.");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data?.error?.message || data?.detail || data?.message || "The request failed.";
      throw new Error(message);
    }
    return data;
  }

  function setStatus(elementId, message, isError = false) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.textContent = message;
    element.classList.toggle("status-error-text", Boolean(isError));
  }

  function makeText(tag, className, value) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = value == null ? "" : String(value);
    return element;
  }

  function makeButton(label, className, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  function renderProjects(items) {
    projects = items;
    projectList.replaceChildren();
    missionProject.replaceChildren(new Option("No project", ""));
    items.forEach((project) => {
      missionProject.add(new Option(project.name, String(project.id)));
      const card = document.createElement("article");
      card.className = "workspace-card";
      card.append(
        makeText("h4", "", project.name),
        makeText("p", "", project.description || "No description provided."),
        makeText("p", "workspace-meta", "Status: " + project.status)
      );
      const actions = document.createElement("div");
      actions.className = "workspace-card-actions";
      actions.appendChild(makeButton("Archive", "btn btn-secondary", async () => {
        if (!window.confirm("Archive project “" + project.name + "”? It will no longer appear as active work.")) return;
        try {
          await api("/api/v1/projects/" + encodeURIComponent(project.id), { method: "DELETE" });
          await refreshProjects();
          await refreshMissions();
          setStatus("workspaceDashboardStatus", "Project archived.");
        } catch (error) {
          setStatus("workspaceDashboardStatus", error.message, true);
        }
      }));
      card.appendChild(actions);
      projectList.appendChild(card);
    });
    if (!items.length) projectList.appendChild(makeText("p", "workspace-empty", "No projects yet. Create one above."));
  }

  function renderMissions(items) {
    missionList.replaceChildren();
    items.forEach((mission) => {
      const card = document.createElement("article");
      card.className = "workspace-card";
      card.append(
        makeText("h4", "", mission.objective),
        makeText("p", "", "Status: " + mission.status + " · Priority: " + mission.priority),
        makeText("p", "workspace-meta", mission.project_name ? "Project: " + mission.project_name : "No project assigned"),
        makeText("p", "workspace-meta", "Created: " + mission.created_at)
      );
      if (Array.isArray(mission.runs) && mission.runs.length) {
        const latest = mission.runs[0];
        card.appendChild(makeText("p", "workspace-meta", "Latest tracking record: " + latest.status));
      }
      missionList.appendChild(card);
    });
    if (!items.length) missionList.appendChild(makeText("p", "workspace-empty", "No missions yet. Record an objective above."));
  }

  async function refreshProjects() {
    const data = await api("/api/v1/projects");
    renderProjects(data.projects || []);
  }

  async function refreshMissions() {
    const data = await api("/api/v1/missions");
    renderMissions(data.missions || []);
  }

  projectForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.getElementById("projectName").value.trim();
    const description = document.getElementById("projectDescription").value.trim();
    if (!name) return;
    const submit = projectForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    setStatus("projectFormStatus", "Creating project…");
    try {
      await api("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name, description: description || null }),
      });
      projectForm.reset();
      await refreshProjects();
      setStatus("projectFormStatus", "Project created.");
    } catch (error) {
      setStatus("projectFormStatus", error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  missionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const objective = document.getElementById("missionObjective").value.trim();
    const projectValue = missionProject.value;
    const priority = document.getElementById("missionPriority").value;
    if (!objective) return;
    const submit = missionForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    setStatus("missionFormStatus", "Saving mission…");
    try {
      await api("/api/v1/missions", {
        method: "POST",
        body: JSON.stringify({
          objective,
          priority,
          project_id: projectValue ? Number(projectValue) : null,
        }),
      });
      missionForm.reset();
      await refreshMissions();
      setStatus("missionFormStatus", "Mission saved. This currently records and tracks the objective; autonomous execution is not connected yet.");
    } catch (error) {
      setStatus("missionFormStatus", error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  async function initialize() {
    try {
      await Promise.all([refreshProjects(), refreshMissions()]);
    } catch (error) {
      dashboardStatus.textContent = error.message;
      dashboardStatus.classList.add("status-error-text");
    }
  }

  initialize();
})();
