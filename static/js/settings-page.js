(function () {
  const preferences = window.SmartBethGPreferences;
  const buttons = [...document.querySelectorAll("[data-setting]")];
  const mentor = document.getElementById("mentorSetting");
  const mentorStatus = document.getElementById("mentorStatus");
  const values = preferences.read();
  function markSelected() {
    buttons.forEach((button) => {
      button.classList.toggle("is-selected", values[button.dataset.setting] === button.dataset.value);
    });
  }
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.setting;
      values[key] = button.dataset.value;
      preferences.save({ [key]: button.dataset.value });
      markSelected();
    });
  });
  mentor.checked = values.mentor !== false;
  mentor.addEventListener("change", () => {
    preferences.save({ mentor: mentor.checked });
    mentorStatus.textContent = "Learning preference saved on this device.";
  });
  markSelected();
})();