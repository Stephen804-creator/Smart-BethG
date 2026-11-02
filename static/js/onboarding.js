(function () {
  const slides = [
    { title: "Meet Smart BethG", description: "Your AI work partner that helps you create, build, and understand the work along the way." },
    { title: "Do real work", description: "Turn ideas into reports, presentations, apps, websites, and other useful work—one stage at a time." },
    { title: "Connect your tools", description: "Bring the tools you already use into your workspace when you are ready. You stay in control of every connection." },
    { title: "You choose how it works", description: "Plan first, work in Balanced mode, or Build. Smart BethG adapts to the way you want to work." }
  ];
  const title = document.getElementById("onboardingTitle");
  const description = document.getElementById("onboardingDescription");
  const step = document.getElementById("onboardingStep");
  const next = document.getElementById("onboardingNext");
  const back = document.getElementById("onboardingBack");
  const skip = document.getElementById("skipOnboarding");
  const splash = document.getElementById("onboardingSplash");
  const slidesContainer = document.getElementById("onboardingSlides");
  const start = document.getElementById("onboardingStart");
  const stage = document.querySelector(".onboarding-stage");
  const dots = [...document.querySelectorAll("[data-slide]")];
  let index = 0;
  let touchStartX = null;

  function finish() {
    window.localStorage.setItem("sbg:onboardingSeen", "1");
    window.location.href = "/login?mode=register";
  }
  function render() {
    const slide = slides[index];
    title.textContent = slide.title;
    description.textContent = slide.description;
    step.textContent = "WELCOME · " + (index + 1) + " OF " + slides.length;
    back.disabled = index === 0;
    next.innerHTML = index === slides.length - 1 ? "Create account <i class='fa-solid fa-arrow-right'></i>" : "Next <i class='fa-solid fa-arrow-right'></i>";
    dots.forEach((dot, i) => {
      dot.classList.toggle("is-active", i === index);
      if (i === index) dot.setAttribute("aria-current", "step");
      else dot.removeAttribute("aria-current");
    });
  }
  start.addEventListener("click", () => {
    splash.hidden = true;
    slidesContainer.hidden = false;
    skip.hidden = false;
    render();
  });
  stage.addEventListener("touchstart", (event) => {
    touchStartX = event.changedTouches[0].clientX;
  }, { passive: true });
  stage.addEventListener("touchend", (event) => {
    if (touchStartX === null) return;
    const delta = event.changedTouches[0].clientX - touchStartX;
    touchStartX = null;
    if (delta < -45 && index < slides.length - 1) { index += 1; render(); }
    else if (delta > 45 && index > 0) { index -= 1; render(); }
  }, { passive: true });
  next.addEventListener("click", () => {
    if (index === slides.length - 1) { finish(); return; }
    index += 1; render();
  });
  back.addEventListener("click", () => { if (index > 0) { index -= 1; render(); } });
  skip.addEventListener("click", finish);
  dots.forEach((dot) => dot.addEventListener("click", () => { index = Number(dot.dataset.slide); render(); }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" && index < slides.length - 1) { index += 1; render(); }
    if (event.key === "ArrowLeft" && index > 0) { index -= 1; render(); }
  });
  render();
})();