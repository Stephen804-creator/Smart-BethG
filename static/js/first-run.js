(function () {
  try {
    if (!window.localStorage.getItem("sbg:onboardingSeen")) {
      window.location.replace("/onboarding");
    }
  } catch (_) {
    // If browser storage is unavailable, keep the account screen accessible.
  }
})();