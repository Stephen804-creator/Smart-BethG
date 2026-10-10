(function () {
  const prefix = String(window.SMART_BETHG_API_PREFIX || "/api/v1").replace(/\/$/, "");
  const list = document.getElementById("artifactList");
  const listStatus = document.getElementById("artifactListStatus");
  const textForm = document.getElementById("textArtifactForm");
  const binaryForm = document.getElementById("binaryArtifactForm");
  if (!list || !textForm || !binaryForm) return;
  let artifacts = [];

  const $ = (selector, root = document) => root.querySelector(selector);
  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined && text !== null) el.textContent = String(text);
    return el;
  }

  async function csrfToken() {
    const response = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error("Could not obtain a security token. Refresh and sign in again.");
    const data = await response.json();
    if (!data.csrf_token) throw new Error("Security token is missing.");
    return data.csrf_token;
  }

  async function api(path, options = {}) {
    const headers = Object.assign({ Accept: "application/json" }, options.headers || {});
    const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
    if (options.body !== undefined && !isForm) headers["Content-Type"] = "application/json";
    if (options.method && !["GET", "HEAD", "OPTIONS"].includes(options.method.toUpperCase())) {
      headers["X-CSRF-Token"] = await csrfToken();
    }
    const response = await fetch(prefix + path, Object.assign({
      credentials: "same-origin", cache: "no-store", headers,
    }, options, { headers }));
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Your session expired. Sign in again.");
    }
    if (!response.ok) {
      throw new Error(String(data.detail || data.error?.message || data.message || "Request failed."));
    }
    return data;
  }

  function formatBytes(value) {
    const bytes = Number(value || 0);
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KiB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MiB";
  }

  function downloadUrl(id) {
    return prefix + "/artifacts/" + encodeURIComponent(id) + "/download";
  }

  async function previewArtifact(artifact, preview, button) {
    if (artifact.artifact_type === "binary") return;
    button.disabled = true;
    try {
      const response = await fetch(prefix + "/artifacts/" + encodeURIComponent(artifact.id) + "/content", {
        credentials: "same-origin", cache: "no-store",
      });
      if (!response.ok) {
        let data = {};
        try { data = await response.json(); } catch (_) {}
        throw new Error(data.detail || "Preview is unavailable.");
      }
      const content = await response.text();
      preview.hidden = false;
      preview.textContent = content;
      button.textContent = "Hide preview";
    } catch (error) {
      preview.hidden = false;
      preview.textContent = error.message;
    } finally { button.disabled = false; }
  }

  function renderArtifact(artifact) {
    const card = node("article", "artifact-item");
    card.append(node("h3", "", artifact.name));
    card.append(node("p", "muted", artifact.created_at ? new Date(artifact.created_at).toLocaleString() : "Saved artifact"));
    const meta = node("div", "artifact-meta");
    meta.append(node("span", "artifact-pill", artifact.artifact_type || "file"));
    meta.append(node("span", "artifact-pill", formatBytes(artifact.size_bytes)));
    if (artifact.content_type) meta.append(node("span", "artifact-pill", artifact.content_type));
    if (artifact.source_type) meta.append(node("span", "artifact-pill", "source: " + artifact.source_type));
    if (artifact.provider) meta.append(node("span", "artifact-pill", "provider: " + artifact.provider));
    if (artifact.model) meta.append(node("span", "artifact-pill", "model: " + artifact.model));
    card.append(meta);
    if (artifact.checksum_sha256) {
      card.append(node("p", "muted small", "SHA-256: " + String(artifact.checksum_sha256).slice(0, 16) + "…"));
    }

    const actions = node("div", "artifact-actions");
    const download = node("a", "btn", "Download");
    download.href = downloadUrl(artifact.id);
    download.setAttribute("download", "");
    actions.append(download);

    const preview = node("pre", "artifact-preview");
    preview.hidden = true;
    if (artifact.artifact_type !== "binary") {
      const previewButton = node("button", "btn", "Preview");
      previewButton.type = "button";
      previewButton.addEventListener("click", async () => {
        if (!preview.hidden) {
          preview.hidden = true;
          preview.textContent = "";
          previewButton.textContent = "Preview";
          return;
        }
        await previewArtifact(artifact, preview, previewButton);
      });
      actions.append(previewButton);
    }

    const remove = node("button", "btn", "Delete");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      if (!window.confirm("Delete this artifact permanently from the active storage backend?")) return;
      remove.disabled = true;
      try {
        await api("/artifacts/" + encodeURIComponent(artifact.id), { method: "DELETE" });
        listStatus.textContent = "Artifact deleted.";
        await loadArtifacts();
      } catch (error) {
        listStatus.textContent = error.message;
      } finally { remove.disabled = false; }
    });
    actions.append(remove);
    card.append(actions, preview);
    return card;
  }

  function renderList() {
    const query = String($("#artifactSearch").value || "").trim().toLowerCase();
    const filtered = artifacts.filter(item =>
      [item.name, item.artifact_type, item.content_type].some(value => String(value || "").toLowerCase().includes(query))
    );
    list.replaceChildren();
    if (!filtered.length) {
      list.append(node("p", "empty-state", artifacts.length ? "No artifacts match this search." : "No artifacts yet. Create a text artifact or upload a file above."));
      return;
    }
    filtered.forEach(item => list.append(renderArtifact(item)));
  }

  async function loadArtifacts() {
    list.replaceChildren(node("p", "muted", "Loading artifacts…"));
    try {
      const data = await api("/artifacts");
      artifacts = data.artifacts || [];
      renderList();
      listStatus.textContent = artifacts.length + " artifact(s) in your library.";
    } catch (error) {
      list.replaceChildren(node("p", "status-message", error.message));
      listStatus.textContent = "Could not load artifacts.";
    }
  }

  textForm.addEventListener("submit", async event => {
    event.preventDefault();
    const status = $("#textArtifactStatus");
    const button = $("#createTextArtifact");
    button.disabled = true;
    status.textContent = "Saving…";
    const values = new FormData(textForm);
    try {
      await api("/artifacts", {
        method: "POST",
        body: JSON.stringify({
          name: String(values.get("name") || "").trim(),
          artifact_type: String(values.get("artifact_type") || "text"),
          content: String(values.get("content") || ""),
        }),
      });
      textForm.reset();
      status.textContent = "Artifact saved.";
      await loadArtifacts();
    } catch (error) {
      status.textContent = error.message;
    } finally { button.disabled = false; }
  });

  binaryForm.addEventListener("submit", async event => {
    event.preventDefault();
    const status = $("#binaryArtifactStatus");
    const button = $("#uploadArtifact");
    const fileInput = $('input[name="file"]', binaryForm);
    if (!fileInput.files || !fileInput.files[0]) {
      status.textContent = "Choose a file first.";
      return;
    }
    button.disabled = true;
    status.textContent = "Uploading…";
    const data = new FormData(binaryForm);
    try {
      await api("/artifacts/upload", { method: "POST", body: data });
      binaryForm.reset();
      status.textContent = "File uploaded and integrity hash recorded.";
      await loadArtifacts();
    } catch (error) {
      status.textContent = error.message;
    } finally { button.disabled = false; }
  });

  $("#refreshArtifacts").addEventListener("click", loadArtifacts);
  $("#artifactSearch").addEventListener("input", renderList);
  loadArtifacts();
})();
