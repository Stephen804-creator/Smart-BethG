(function () {
  const form = document.getElementById("authForm");
  const errorEl = document.getElementById("authError");
  const modeToggle = document.getElementById("authModeToggle");
  const submitBtn = document.getElementById("authSubmit");
  const title = document.getElementById("authTitle");
  const inviteCodeGroup = document.getElementById("inviteCodeGroup");
  const consentGroup = document.getElementById("consentGroup");
  let mode = "login";
  let policyUpdatePending = false;

  async function getCsrfToken() {
    const res = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!res.ok) throw new Error("Could not obtain CSRF token.");
    const data = await res.json();
    if (!data.csrf_token) throw new Error("CSRF token missing.");
    return data.csrf_token;
  }

  function showPolicyUpdate() {
    policyUpdatePending = true;
    mode = "policy-update";
    title.textContent = "Review updated Smart BethG policies";
    submitBtn.textContent = "Accept and continue";
    modeToggle.hidden = true;
    inviteCodeGroup.hidden = true;
    consentGroup.hidden = false;
    errorEl.textContent = "Our minimum account age is now 18. Review the current Terms and Privacy Policy and confirm that you are at least 18 to continue.";
  }

  function setMode(next) {
    policyUpdatePending = false;
    modeToggle.hidden = false;
    mode = next;
    if (mode === "login") {
      title.textContent = "Log in to Smart BethG";
      submitBtn.textContent = "Log in";
      modeToggle.textContent = "Need an account? Create one";
      inviteCodeGroup.hidden = true;
      consentGroup.hidden = true;
    } else {
      title.textContent = "Create your Smart BethG account";
      submitBtn.textContent = "Create account";
      modeToggle.textContent = "Already have an account? Log in";
      inviteCodeGroup.hidden = true;
      consentGroup.hidden = false;
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

    if (policyUpdatePending) {
      submitBtn.disabled = true;
      try {
        const csrfToken = await getCsrfToken();
        const response = await fetch("/auth/accept-policies", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
          credentials: "same-origin",
          body: JSON.stringify({
            accepted_terms: form.acceptedTerms.checked,
            accepted_privacy: form.acceptedPrivacy.checked,
            age_verified: form.ageVerified.checked,
          }),
        });
        const data = await response.json();
        if (!response.ok || !data.accepted) {
          errorEl.textContent = data.detail || "Could not record your updated policy acceptance.";
          return;
        }
        window.location.href = "/";
      } catch (err) {
        errorEl.textContent = "Could not reach Smart BethG. Please try again.";
      } finally {
        submitBtn.disabled = false;
      }
      return;
    }

    if (mode === "register") {
      const acceptedTerms = form.acceptedTerms.checked;
      const acceptedPrivacy = form.acceptedPrivacy.checked;
      const ageVerified = form.ageVerified.checked;
      if (!acceptedTerms || !acceptedPrivacy || !ageVerified) {
        errorEl.textContent = "You must accept the Terms, Privacy Policy, and confirm you are at least 18 years old.";
        return;
      }
    }

    submitBtn.disabled = true;
    try {
      const csrfToken = await getCsrfToken();
      if (mode === "register") {
        const inviteCode = form.inviteCode ? form.inviteCode.value.trim() : "";
        const res = await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
          credentials: "same-origin",
          body: JSON.stringify({
            username,
            password,
            invite_code: inviteCode || null,
            accepted_terms: form.acceptedTerms.checked,
            accepted_privacy: form.acceptedPrivacy.checked,
            age_verified: form.ageVerified.checked,
          }),
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
      if (loginData.policy_update_required) {
        showPolicyUpdate();
        return;
      }
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
  if (new URLSearchParams(window.location.search).get("policy_update") === "1") {
    showPolicyUpdate();
  }

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

