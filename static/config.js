/* How the dashboard reaches its data.
 *
 * "live"   -- the FastAPI app serves this page and the API from one origin,
 *             so calls go to /api/... on that origin. This is the committed
 *             value: `make run`, `make up` and any real deployment use it.
 *
 * "static" -- no server, only files. Not currently used: GitHub Pages publishes
 *             the landing page only, because results are for approved users.
 *
 * Set window.API_BASE here to point the dashboard at an API on a different
 * host (it must send CORS headers; app/main.py already does).
 */
window.API_MODE = "live";
