(function () {
  const form = document.getElementById("authForm");
  const errorEl = document.getElementById("authError");
  const modeToggle = document.getElementById("authModeToggle");
  const submitBtn = document.getElementById("authSubmit");
  const title = document.getElementById("authTitle");
  const inviteCodeGroup = document.getElementById("inviteCodeGroup");
  let mode = "login";

  async function getCsrfToken() {
    const res = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!res.ok) throw new Error("Could not obtain CSRF token.");
    const data = await res.json();
    if (!data.csrf_token) throw new Error("CSRF token missing.");
    return data.csrf_token;
  }

  function setMode(next) {
    mode = next;
    if (mode === "login") {
      title.textContent = "Log in to Smart BethG";
      submitBtn.textContent = "Log in";
      modeToggle.textContent = "Need an account? Create one";
      inviteCodeGroup.hidden = true;
    } else {
      title.textContent = "Create your Smart BethG account";
      submitBtn.textContent = "Create account";
      modeToggle.textContent = "Already have an account? Log in";
      inviteCodeGroup.hidden = false;
    }
    errorEl.textContent = "";
  }

  modeToggle.addEventListener("click", (e) => {
    e.preventDefault();
    setMode(mode === "login" ? "register" : "login");
  });

  const toggleBtn = document.getElementById("togglePassword");
  const passwordInput = document.getElementById("password");
  if (toggleBtn && passwordInput) {
    toggleBtn.addEventListener("click", () => {
      const showing = passwordInput.type === "text";
      passwordInput.type = showing ? "password" : "text";
      toggleBtn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      toggleBtn.innerHTML = showing
        ? '<i class="fa-solid fa-eye" aria-hidden="true"></i>'
        : '<i class="fa-solid fa-eye-slash" aria-hidden="true"></i>';
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";
    const username = form.username.value.trim();
    const password = form.password.value;

    submitBtn.disabled = true;
    try {
      const csrfToken = await getCsrfToken();
      if (mode === "register") {
        const inviteCode = form.inviteCode.value.trim();
        const res = await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
          credentials: "same-origin",
          body: JSON.stringify({ username, password, invite_code: inviteCode || null }),
        });
        const data = await res.json();
        if (!res.ok) {
          errorEl.textContent = (data.error && data.error.message) || data.detail || "Could not create account.";
          return;
        }
      }

      const loginRes = await fetch("/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ username, password }),
      });
      const loginData = await loginRes.json();
      if (!loginRes.ok || !loginData.authenticated) {
        errorEl.textContent = (loginData.error && loginData.error.message) || loginData.detail || loginData.error || "Invalid username or password.";
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

  fetch("/auth/config")
    .then((r) => r.json())
    .then((data) => {
      if (data.google_oauth_enabled) {
        document.getElementById("googleAuthDivider").hidden = false;
        document.getElementById("googleAuthButton").hidden = false;
      }
    })
    .catch(() => {});
})();
