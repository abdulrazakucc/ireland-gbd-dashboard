// Apply a saved appearance before the first paint. An external file rather than
// an inline script, so the Content-Security-Policy needs no exception for it.
try {
  var saved = localStorage.getItem("ucc-gbd-theme");
  if (saved === "dark" || saved === "light") document.documentElement.dataset.theme = saved;
} catch (e) {
  /* storage unavailable: follow the operating system */
}
