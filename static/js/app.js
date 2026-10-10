// Smart BethG - shared application behaviour (sidebar toggle).
// CSS owns presentation; this file owns behaviour, matching the contract
// documented in CSS/main.css above the .sidebar-collapsed rules.
(function () {
  const toggle = document.getElementById("sidebarToggle");
  const app = document.querySelector(".app");
  if (!toggle || !app) return;

  const stored = window.localStorage.getItem("sbg:sidebarCollapsed") === "1";
  if (stored) app.classList.add("sidebar-collapsed");

  toggle.addEventListener("click", () => {
    const collapsed = app.classList.toggle("sidebar-collapsed");
    window.localStorage.setItem("sbg:sidebarCollapsed", collapsed ? "1" : "0");
    toggle.setAttribute("aria-expanded", String(!collapsed));
  });

  const logoutBtn = document.getElementById("logoutButton");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      try {
        const csrfResponse = await fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" });
        if (!csrfResponse.ok) throw new Error("CSRF token request failed.");
        const csrfData = await csrfResponse.json();
        const logoutResponse = await fetch("/auth/logout", {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-CSRF-Token": csrfData.csrf_token },
        });
        if (!logoutResponse.ok) throw new Error("Logout request failed.");
        window.location.href = "/login";
      } catch (err) {
        window.alert("Could not log out securely. Refresh the page and try again.");
      }
    });
  }
})();
