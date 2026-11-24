// Runs before first paint (classic script in <head>) so the saved theme applies with no flash.
(function () {
  try {
    var pref = localStorage.getItem("orbit-theme") || "system";
    var dark = pref === "dark" || (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme-pref", pref);
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
