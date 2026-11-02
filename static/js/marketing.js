(function () {
  const button=document.getElementById("marketingMenuButton"),menu=document.getElementById("marketingMenu");
  if(!button||!menu)return;
  function setOpen(open){menu.hidden=!open;button.setAttribute("aria-expanded",String(open));button.setAttribute("aria-label",open?"Close website menu":"Open website menu");}
  button.addEventListener("click",()=>setOpen(menu.hidden));
  menu.querySelectorAll("a").forEach((link)=>link.addEventListener("click",()=>setOpen(false)));
  document.addEventListener("click",(event)=>{if(!menu.contains(event.target)&&!button.contains(event.target))setOpen(false);});
  document.addEventListener("keydown",(event)=>{if(event.key==="Escape")setOpen(false);});
})();