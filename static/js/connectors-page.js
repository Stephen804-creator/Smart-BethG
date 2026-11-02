(function () {
  const list = document.getElementById("connectorList");
  const search = document.getElementById("connectorSearch");
  const status = document.getElementById("connectorStatus");
  const categoryButtons = [...document.querySelectorAll("[data-category]")];
  let catalog = [];
  let installed = [];
  let category = "all";
  async function csrf() {
    const response = await fetch("/auth/csrf", { credentials:"same-origin", cache:"no-store" });
    if (!response.ok) throw new Error("CSRF token unavailable.");
    return (await response.json()).csrf_token;
  }
  async function request(url, options={}) {
    const headers = { ...(options.headers || {}) };
    if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = await csrf();
    const response = await fetch(url, { credentials:"same-origin", ...options, headers });
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (response.status === 401) { window.location.href="/login"; throw new Error("Please sign in again."); }
    if (!response.ok) throw new Error(data.detail || "Connector request failed.");
    return data;
  }
  function installationFor(connector) { return installed.find((item) => item.connector_key === connector.key); }
  function render() {
    const q = search.value.trim().toLowerCase();
    const filtered = catalog.filter((item) => (category === "all" || item.category === category) &&
      (item.name.toLowerCase().includes(q) || item.key.toLowerCase().includes(q) || item.category.toLowerCase().includes(q)));
    list.replaceChildren();
    if (!filtered.length) {
      const empty = document.createElement("p"); empty.className="subpage-empty"; empty.textContent="No connectors match this search."; list.appendChild(empty); return;
    }
    filtered.forEach((item) => {
      const install = installationFor(item);
      const card = document.createElement("article"); card.className="connector-card";
      const main = document.createElement("div"); main.className="connector-row";
      const logo = document.createElement("span"); logo.className="connector-logo"; logo.textContent=item.name.slice(0,1).toUpperCase();
      const text = document.createElement("div"); text.className="connector-copy";
      const title = document.createElement("h2"); title.textContent=item.name;
      const note = document.createElement("p"); note.textContent= item.category.charAt(0).toUpperCase()+item.category.slice(1).replace("-"," ")+" · "+(item.actions||[]).length+" available actions";
      text.append(title,note);
      const isActive = Boolean(install && (install.status === "connected" || item.key === "smartbethg"));
      const action = document.createElement("button"); action.type="button"; action.className=isActive?"connector-connected":"connector-connect";
      if (isActive) { action.innerHTML='<i class="fa-solid fa-check"></i>'; action.setAttribute("aria-label","Connected"); action.title="Connected"; }
      else { action.textContent=install?"Connect":"+"; action.setAttribute("aria-label",install?"Connect "+item.name:"Add "+item.name); action.title=action.getAttribute("aria-label"); }
      action.addEventListener("click",()=>connect(item,install,action));
      main.append(logo,text,action);
      const details = document.createElement("details"); details.className="connector-details";
      const summary = document.createElement("summary"); summary.textContent="Details and permissions";
      const body = document.createElement("div"); body.className="connector-detail-body";
      const desc = document.createElement("p"); desc.textContent=item.adapter_available ? (item.oauth_configured ? "This connector is available and its authorization is configured for this deployment." : "This connector is registered, but external authorization is not configured on this deployment.") : "The adapter is not available in this deployment.";
      const actionsTitle = document.createElement("strong"); actionsTitle.textContent="Available actions";
      const actionsList = document.createElement("ul");
      (item.actions||[]).forEach((entry)=>{const li=document.createElement("li");li.textContent=entry.permission||entry.action||String(entry);actionsList.appendChild(li);});
      body.append(desc,actionsTitle,actionsList);
      if (install) { const dis=document.createElement("button");dis.type="button";dis.className="connector-disconnect";dis.textContent="Disconnect";dis.addEventListener("click",()=>disconnect(install,dis));body.appendChild(dis); }
      details.append(summary,body);card.append(main,details);list.appendChild(card);
    });
  }
  async function connect(item, install, button) {
    button.disabled=true; status.textContent="Preparing "+item.name+"…";
    try {
      let current=install;
      if (!current) {
        current=await request("/api/v1/connectors",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({connector_key:item.key,permissions:item.key==="smartbethg"?["smartbethg.knowledge.search"]:[]})});
        installed.push(current);
      }
      if (item.key === "smartbethg") {
        status.textContent="Smart BethG Knowledge was added. No external sign-in is required.";
        render(); return;
      }
      if (!item.oauth_configured) {
        status.textContent="Added "+item.name+", but authorization is not configured for this deployment.";
        render(); return;
      }
      const started=await request("/api/v1/connectors/"+encodeURIComponent(current.id)+"/oauth/start",{method:"POST"});
      if (!started.authorization_url) throw new Error("The provider did not return an authorization link.");
      window.location.href=started.authorization_url;
    } catch (error) { status.textContent=error.message; }
    finally { button.disabled=false; }
  }
  async function disconnect(install,button) {
    button.disabled=true;
    try { await request("/api/v1/connectors/"+encodeURIComponent(install.id),{method:"DELETE"});installed=installed.filter((x)=>x.id!==install.id);status.textContent="Connector disconnected.";render(); }
    catch(error){status.textContent=error.message;button.disabled=false;}
  }
  async function load() {
    try {
      const results=await Promise.all([request("/api/v1/connectors/catalog"),request("/api/v1/connectors")]);
      catalog=results[0].connectors||[];installed=results[1].connectors||[];
      render();
      const params=new URLSearchParams(window.location.search);
      if(params.get("connector_oauth")==="connected")status.textContent="Connector authorization completed for "+(params.get("provider")||"the selected service")+".";
      else if(params.get("connector_oauth")==="denied")status.textContent="Connector authorization was cancelled or denied.";
    } catch(error) { list.innerHTML='<p class="subpage-error">Connectors could not be loaded. Refresh to try again.</p>';status.textContent=error.message; }
  }
  search.addEventListener("input",render);
  categoryButtons.forEach((button)=>button.addEventListener("click",()=>{category=button.dataset.category;categoryButtons.forEach((b)=>b.classList.toggle("is-selected",b===button));render();}));
  load();
})();