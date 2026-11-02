(function () {
  const KEY="sbg:systemInstructions";const textarea=document.getElementById("userInstructions"),count=document.getElementById("instructionCount"),status=document.getElementById("instructionStatus");
  try{textarea.value=window.localStorage.getItem(KEY)||"";}catch(_){}
  function updateCount(){count.textContent=textarea.value.length.toLocaleString()+" / 4,000";}
  textarea.addEventListener("input",updateCount);
  document.getElementById("saveInstructions").addEventListener("click",()=>{try{window.localStorage.setItem(KEY,textarea.value.trim());status.textContent="Instructions saved on this device and will be included with your AI chat requests."; }catch(_){status.textContent="Could not save instructions in this browser.";}});
  document.getElementById("resetInstructions").addEventListener("click",()=>{textarea.value="";try{window.localStorage.removeItem(KEY);status.textContent="Instructions cleared."; }catch(_){status.textContent="Could not clear saved instructions.";}updateCount();});
  updateCount();
})();