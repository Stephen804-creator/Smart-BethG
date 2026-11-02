(function () {
  const list=document.getElementById("artifactList"), empty=document.getElementById("artifactEmpty"), viewer=document.getElementById("artifactViewer");
  const title=document.getElementById("artifactTitle"), preview=document.getElementById("artifactPreview"), htmlPreview=document.getElementById("artifactHtmlPreview"), code=document.getElementById("artifactCode"), codeText=document.getElementById("artifactCodeText"), fileName=document.getElementById("artifactFileName"), status=document.getElementById("artifactStatus");
  const menuButton=document.getElementById("artifactMenuButton"), menu=document.getElementById("artifactActionsMenu");
  let artifacts=[], selected=null, content="", activeView="preview", hasHtmlPreview=false;
  async function get(url) {
    const response=await fetch(url,{credentials:"same-origin",cache:"no-store"});
    if(response.status===401){window.location.href="/login";throw new Error("Please sign in again.");}
    if(!response.ok)throw new Error("Artifact request failed.");
    return response;
  }
  async function loadContent(item) {
    selected=item; content="";
    try {
      const response=await get("/api/v1/artifacts/"+encodeURIComponent(item.id)+"/content");
      content=await response.text();
      title.textContent=item.name||"Artifact"; fileName.textContent=item.name||"artifact.txt";
      const contentType=String(item.content_type||"").toLowerCase();
      const artifactType=String(item.artifact_type||"").toLowerCase();
      const isHtml=contentType.includes("text/html")||["html","website","webpage"].includes(artifactType);
      hasHtmlPreview=isHtml;
      if(isHtml){
        const csp='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data: blob:; style-src \'unsafe-inline\'">';
        const lowerContent=content.toLowerCase();
        htmlPreview.srcdoc=lowerContent.includes("<head")
          ? content.replace(/<head[^>]*>/i,(head)=>head+csp)
          : "<!doctype html><html><head>"+csp+"</head><body>"+content+"</body></html>";
        htmlPreview.hidden=false;preview.hidden=true;
      }else{
        htmlPreview.removeAttribute("srcdoc");htmlPreview.hidden=true;preview.textContent=content;preview.hidden=false;
      }
      codeText.textContent=content;
      updateView();
      empty.hidden=true;viewer.hidden=false;status.textContent="";
      list.querySelectorAll("button").forEach((b)=>b.classList.toggle("is-selected",b.dataset.id===String(item.id)));
    } catch(error) { status.textContent=error.message; }
  }
  async function load() {
    try {
      const response=await get("/api/v1/artifacts");
      const data=await response.json(); artifacts=data.artifacts||[]; list.replaceChildren();
      if(!artifacts.length){list.innerHTML='<p class="subpage-empty">Artifacts you create will appear here.</p>';return;}
      artifacts.forEach((item)=>{
        const button=document.createElement("button");button.type="button";button.dataset.id=String(item.id);
        const icon=document.createElement("i");icon.className="fa-regular fa-file-code";
        const name=document.createElement("span");name.textContent=item.name||"Untitled artifact";
        button.append(icon,name);button.addEventListener("click",()=>loadContent(item));list.appendChild(button);
      });
      loadContent(artifacts[0]);
    } catch(error) { list.innerHTML='<p class="subpage-error">Artifacts could not be loaded.</p>';status.textContent=error.message; }
  }
  function updateView(){
    const isCode=activeView==="code";
    code.hidden=!isCode;
    if(isCode){preview.hidden=true;htmlPreview.hidden=true;}
    else if(hasHtmlPreview){preview.hidden=true;htmlPreview.hidden=false;}
    else{preview.hidden=false;htmlPreview.hidden=true;}
  }
  document.querySelectorAll("[data-view]").forEach((button)=>button.addEventListener("click",()=>{
    activeView=button.dataset.view;
    document.querySelectorAll("[data-view]").forEach((b)=>{b.classList.toggle("is-selected",b===button);b.setAttribute("aria-selected",String(b===button));});
    updateView();
  }));
  menuButton.addEventListener("click",()=>{menu.hidden=!menu.hidden;menuButton.setAttribute("aria-expanded",String(!menu.hidden));});
  document.addEventListener("click",(event)=>{if(!menu.contains(event.target)&&!menuButton.contains(event.target)){menu.hidden=true;menuButton.setAttribute("aria-expanded","false");}});
  document.getElementById("artifactDownload").addEventListener("click",()=>{
    if(!selected)return;const blob=new Blob([content],{type:"text/plain;charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=(selected.name||"artifact").replace(/[^a-z0-9._-]/gi,"_")+".txt";a.click();URL.revokeObjectURL(url);menu.hidden=true;
  });
  document.getElementById("artifactCopyLink").addEventListener("click",async()=>{
    if(!selected)return;const url=window.location.origin+"/workspace/artifacts?id="+encodeURIComponent(selected.id);
    try{await navigator.clipboard.writeText(url);status.textContent="Artifact link copied."; }catch(_){status.textContent="Clipboard access is unavailable in this browser.";}menu.hidden=true;
  });
  const id=new URLSearchParams(window.location.search).get("id");
  load().then(()=>{if(id){const item=artifacts.find((x)=>String(x.id)===id);if(item)loadContent(item);}});
})();