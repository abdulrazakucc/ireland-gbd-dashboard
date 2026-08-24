/* How the dashboard reaches its data.
 *
 * "live"   -- the FastAPI app serves this page and the API from one origin,
 *             so calls go to /api/... on that origin. This is the committed
 *             value: `make run`, `make up` and any real deployment use it.
 *
 * "static" -- there is no server, only the files of a published snapshot.
 *             scripts/build_static_site.py overwrites this file with that
 *             mode when it assembles the snapshot for GitHub Pages.
 *
 * Set window.API_BASE here to point the dashboard at an API on a different
 * host (it must send CORS headers; app/main.py already does).
 */
window.API_MODE = "live";
