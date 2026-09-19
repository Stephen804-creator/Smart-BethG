(function () {
  const form = document.getElementById("authForm");
  const errorEl = document.getElementById("authError");
  const modeToggle = document.getElementById("authModeToggle");
  const submitBtn = document.getElementById("authSubmit");
  const title = document.getElementById("authTitle");
  const inviteCodeGroup = document.getElementById("inviteCodeGroup");
  let mode = "login";

  function setMode(next) {
    mode = next;
    if (mode === "login") {
      title.textContent = "Log in to Smart BethG";
      submitBtn.textContent = "Log in";
      modeToggle.textContent = "Need an account? Create one";
      inviteCodeGroup.style.display = "none";
    } else {
      title.textContent = "Create your Smart BethG account";
      submitBtn.textContent = "Create account";
      modeToggle.textContent = "Already have an account? Log in";
      inviteCodeGroup.style.display = "block";
    }
    errorEl.textContent = "";
  }

  modeToggle.addEventListener("click", (e) => {
    e.preventDefault();
    setMode(mode === "login" ? "register" : "login");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";
    const username = form.username.value.trim();
    const password = form.password.value;

    submitBtn.disabled = true;
    try {
      if (mode === "register") {
        const inviteCode = form.inviteCode.value.trim();
        const res = await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password, invite_code: inviteCode || null }),
        });
        const data = await res.json();
        if (!res.ok) {
          errorEl.textContent = data.detail || "Could not create account.";
          return;
        }
      }

      const loginRes = await fetch("/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const loginData = await loginRes.json();
      if (!loginRes.ok || !loginData.authenticated) {
        errorEl.textContent = loginData.detail || loginData.error || "Invalid username or password.";
        return;
      }
      window.location.href = "/";
    } catch (err) {
      errorEl.textContent = "Could not reach Smart BethG. Please try again.";
    } finally {
      submitBtn.disabled = false;
    }
  });

  setMode("login");
})();
