/* Plain-language onboarding. The steps describe user actions, not internal implementation. */
(() => {
  const dialog = document.getElementById("onboardingDialog");
  if (!dialog) return;
  const $ = (id) => document.getElementById(id);
  const steps = [
    { title:"Welcome to Smart BethG", description:"A workspace for thinking through tasks, having conversations, and organizing work with an AI assistant.", tip:"Start with what you want to achieve. You do not need special commands.", icon:"fa-compass", caption:"Your ideas, in one workspace" },
    { title:"Tell it what you want to do", description:"Describe a question, problem, idea, or task in your own words. Include the result you want and any useful context.", tip:"Example: “Help me plan my next project and break it into manageable steps.”", icon:"fa-message", caption:"Start with a clear request" },
    { title:"Work through the conversation", description:"Read the response, ask follow-up questions, correct anything that missed the point, and refine the result together.", tip:"You can clarify your request at any time. You do not have to get everything right on the first try.", icon:"fa-comments", caption:"Ask, clarify, improve" },
    { title:"Keep your work organised", description:"Use Projects & missions to name a larger effort and record objectives you want to keep track of. Open a section only when you need it.", tip:"Use the Workspace menu to jump to projects and missions without searching through a long page.", icon:"fa-folder-open", caption:"Keep related work together" },
    { title:"Review before taking action", description:"When Smart BethG asks you to approve an action, review what it will do before you decide. Some work may need your input or may not be available in every session.", tip:"Only approve an action when its details make sense to you. A suggested action is not the same as a completed action.", icon:"fa-shield-halved", caption:"You stay in control" },
    { title:"Ready when you are", description:"Start a conversation and explain what you would like help with. You can return to this guide any time from the Help button.", tip:"Try this prompt: “Help me plan my next project.”", icon:"fa-rocket", caption:"Choose your next step" }
  ];
  let index = 0;
  let returnFocus = null;
  const title = $("onboardingTitle"), description = $("onboardingDescription");
  const tip = $("onboardingTip"), visualIcon = $("onboardingVisualIcon");
  const caption = $("onboardingVisualCaption"), label = $("onboardingStepLabel");
  const progress = $("onboardingProgressBar"), back = $("onboardingBack");
  const next = $("onboardingNext"), skip = $("onboardingSkip");
  const dots = $("onboardingDots");
  const close = $("onboardingClose");
  const storageKey = "sbg:onboarding-complete:v1";

  function render() {
    const step = steps[index];
    title.textContent = step.title;
    description.textContent = step.description;
    tip.lastElementChild.textContent = step.tip;
    visualIcon.innerHTML = '<i class="fa-solid ' + step.icon + '" aria-hidden="true"></i>';
    caption.textContent = step.caption;
    label.textContent = "STEP " + (index + 1) + " OF " + steps.length;
    progress.style.width = (((index + 1) / steps.length) * 100) + "%";
    back.disabled = index === 0;
    next.innerHTML = index === steps.length - 1
      ? 'Start using Smart BethG <i class="fa-solid fa-arrow-right" aria-hidden="true"></i>'
      : 'Next <i class="fa-solid fa-arrow-right" aria-hidden="true"></i>';
    dots.querySelectorAll("button").forEach((dot, i) => {
      if (i === index) dot.setAttribute("aria-current", "step");
      else dot.removeAttribute("aria-current");
    });
  }
  function finish(markComplete) {
    if (markComplete) {
      try { window.localStorage.setItem(storageKey, "1"); } catch (_) { /* Storage may be disabled; guide still works. */ }
    }
    if (dialog.open) dialog.close();
    if (returnFocus && document.contains(returnFocus)) returnFocus.focus();
  }
  function openGuide() {
    returnFocus = document.activeElement;
    index = 0;
    render();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    close.focus();
  }
  steps.forEach((_, i) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "onboarding-dot";
    dot.setAttribute("aria-label", "Go to step " + (i + 1));
    dot.addEventListener("click", () => { index = i; render(); });
    dots.appendChild(dot);
  });
  $("helpButton")?.addEventListener("click", openGuide);
  back.addEventListener("click", () => { if (index > 0) { index--; render(); } });
  next.addEventListener("click", () => {
    if (index < steps.length - 1) { index++; render(); return; }
    finish(true);
    window.location.href = "{{ url_for('main.chat_page') }}";
  });
  skip.addEventListener("click", () => finish(true));
  close.addEventListener("click", () => finish(false));
  dialog.addEventListener("click", (event) => { if (event.target === dialog) finish(false); });
  dialog.addEventListener("cancel", () => { /* Escape closes the guide without blocking the app. */ });
  try {
    if (!window.localStorage.getItem(storageKey)) {
      window.setTimeout(openGuide, 350);
    }
  } catch (_) { /* If storage is blocked, keep the guide available through Help without forcing it. */ }
  render();
})();
