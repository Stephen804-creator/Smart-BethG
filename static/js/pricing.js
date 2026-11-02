(function () {
  const toggleButtons=[...document.querySelectorAll("[data-pricing]")],subscribe=document.getElementById("subscribePlans"),payg=document.getElementById("paygPlans"),status=document.getElementById("pricingStatus");
  toggleButtons.forEach((button)=>button.addEventListener("click",()=>{
    const mode=button.dataset.pricing;subscribe.hidden=mode!=="subscribe";payg.hidden=mode!=="payg";
    toggleButtons.forEach((item)=>{item.classList.toggle("is-selected",item===button);item.setAttribute("aria-pressed",String(item===button));});
    status.textContent="";
  }));
  document.querySelectorAll("[data-purchase]").forEach((button)=>button.addEventListener("click",()=>{
    status.textContent="Payments are not enabled in this release yet. You can create a free account now.";
  }));
})();