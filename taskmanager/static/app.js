// Progressive enhancement only: the app works without JavaScript.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("select.js-autosubmit").forEach((el) =>
    el.addEventListener("change", () => el.form.submit()));
  document.querySelectorAll("form.js-confirm").forEach((form) =>
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm || "Are you sure?")) e.preventDefault();
    }));
});
