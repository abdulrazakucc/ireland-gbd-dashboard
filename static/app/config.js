/* Where the application gets its results.
 *
 *   "server" -- from this application's API, after signing in. The same on a
 *               laptop (make run / make up) and on a server.
 *   "sealed" -- from the encrypted copy published beside this page on GitHub
 *               Pages, opened in the browser with the reader's credentials.
 *               scripts/build_static_site.py writes that version of this file.
 */
window.GBD_APP = { mode: "server" };
