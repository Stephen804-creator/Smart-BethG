(function () {
  const status=document.getElementById("usageStatus");
  const fmt=(n)=>Number(n||0).toLocaleString();
  async function load(){
    try{
      const response=await fetch("/api/v1/chat/usage",{credentials:"same-origin",cache:"no-store"});
      if(response.status===401){location.href="/login";return;}
      if(!response.ok)throw new Error("Usage data could not be loaded.");
      const data=await response.json();const budget=data.budget||{};
      const limit=Number(budget.daily_token_limit||0), used=Number(budget.tokens_reserved_or_used||0), actual=Number(budget.actual_tokens||0);
      const remaining=Math.max(0,limit-used), percent=limit?Math.min(100,used/limit*100):0;
      document.getElementById("usageLeft").textContent=fmt(remaining);
      document.getElementById("usageUsed").textContent=fmt(used)+" used";
      document.getElementById("usageLimit").textContent=fmt(limit)+" daily limit";
      document.getElementById("usageProgress").style.width=percent+"%";
      document.getElementById("actualTokens").textContent=fmt(actual);
      document.getElementById("usageRequests").textContent=fmt(budget.requests);
      document.getElementById("usageSpend").textContent="$"+Number(budget.estimated_spend_usd||0).toFixed(4);
      const modelList=document.getElementById("usageModels");modelList.replaceChildren();
      const models=data.by_model||[];
      if(!models.length){modelList.innerHTML='<p class="subpage-empty">No recorded model usage yet.</p>';}
      models.forEach((model)=>{const row=document.createElement("article");row.className="usage-model-row";const name=document.createElement("strong");name.textContent=(model.provider||"Unknown provider")+" · "+(model.model||"Unknown model");const count=document.createElement("span");count.textContent=fmt(Number(model.input_tokens||0)+Number(model.output_tokens||0))+" tokens";row.append(name,count);modelList.appendChild(row);});
      status.textContent="Usage period: "+(budget.period_start_utc||"UTC today")+".";
    }catch(error){status.textContent=error.message;}
  }
  load();
})();