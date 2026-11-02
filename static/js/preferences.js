(function () {
  const KEY = "sbg:preferences";
  function read() {
    try { return JSON.parse(window.localStorage.getItem(KEY) || "{}"); }
    catch (_) { return {}; }
  }
  function apply() {
    const prefs = read();
    const root = document.body;
    root.classList.toggle("theme-light", prefs.appearance === "light");
    root.classList.toggle("font-readable", prefs.font === "readable");
    root.classList.toggle("font-mono", prefs.font === "mono");
  }
  window.SmartBethGPreferences = {
    read,
    save(next) {
      const current = read();
      window.localStorage.setItem(KEY, JSON.stringify({ ...current, ...next }));
      apply();
    },
    apply
  };
  apply();
})();