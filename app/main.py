"""
Global Health Evidence -- UCC School of Public Health.

The application entry point. One process serves both halves of the product on
a single port:

* ``/``          the dashboard (the files in ``static/``)
* ``/api/...``   the JSON API   (the routes in ``app/routes.py``)
* ``/docs``      interactive API documentation, generated from the code

Run it:

.. code-block:: console

    make run                                    # or, by hand:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import config
from app.routes import router

__version__ = "3.0.0"

DESCRIPTION = """
Global Burden of Disease estimates across the countries loaded by an approved
research team. The launch dataset covers Ireland and the model is designed to
accept additional locations without code changes. Results are served from a local
database built by the ETL in `etl/`. Every estimate keeps its release, measure,
metric, location, sex, age, cause, risk, year and 95% uncertainty interval.

Start from `/api/series` (what exists) or `/api/dimensions` (which values
exist), then read a series with `/api/trend`, a ranking with `/api/ranked`,
or rows with `/api/estimates`; download with `/api/export.csv`,
`/api/figure.png` and `/api/figure.pdf`.

Maintained by the School of Public Health, University College Cork.
Principal Investigator: Dr. Zubair Kabir.
"""


def _web_origins(values: list[str]) -> list[str]:
    """Validate exact browser origins before using them in CORS or CSP."""
    clean = []
    for value in values:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or parts.username
            or parts.password
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
        ):
            raise RuntimeError(f"Invalid GBD_CORS_ORIGINS entry: {value!r}")
        clean.append(value.rstrip("/"))
    return clean


def _script_hashes(static_dir: Path) -> str:
    """CSP hashes for inline dashboard scripts, avoiding ``unsafe-inline``."""
    index = static_dir / "index.html"
    if not index.is_file():
        return ""
    scripts = re.findall(r"<script>(.*?)</script>", index.read_text(encoding="utf-8"), re.S)
    return " ".join(
        f"'sha256-{base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()}'"
        for script in scripts
    )


def create_app(db_path: Path | None = None, cors_origins: list[str] | None = None) -> FastAPI:
    """Build and return the application.

    A factory rather than a module-level singleton, so the test-suite can
    construct a fresh instance against a temporary database.

    Args:
        db_path: The database to serve. Default: ``config.DB_PATH``.
        cors_origins: Browser origins allowed to call the API cross-site.
            Default: ``GBD_CORS_ORIGINS``, which is empty unless configured.
    """
    if config.ENVIRONMENT not in {"development", "test", "production"}:
        raise RuntimeError("GBD_ENV must be development, test, or production")
    if config.AUTH_MODE not in {"off", "proxy"}:
        raise RuntimeError("GBD_AUTH_MODE must be off or proxy")
    if any("://" in host or "/" in host for host in config.TRUSTED_HOSTS):
        raise RuntimeError("GBD_TRUSTED_HOSTS entries must be hostnames, without schemes or paths")
    if config.ENVIRONMENT == "production" and "*" in config.TRUSTED_HOSTS:
        raise RuntimeError("Production does not allow a wildcard in GBD_TRUSTED_HOSTS")
    if config.AUTH_MODE == "proxy" and (
        not config.AUTH_USER_HEADER or len(config.PROXY_SECRET) < 32
    ):
        raise RuntimeError("Proxy authentication requires a user header and a 32+ character secret")
    if config.ENVIRONMENT == "production" and config.AUTH_MODE != "proxy":
        raise RuntimeError(
            "Production starts only with GBD_AUTH_MODE=proxy and a strong proxy secret"
        )

    origins = _web_origins(config.CORS_ORIGINS if cors_origins is None else cors_origins)
    script_hashes = _script_hashes(config.STATIC_DIR)

    app = FastAPI(
        title="Global Health Evidence API",
        description=DESCRIPTION,
        version=__version__,
        contact={
            "name": "Dr. Zubair Kabir, School of Public Health, UCC",
            "url": "https://research.ucc.ie/en/persons/zubair-kabir/",
        },
        docs_url="/docs" if config.EXPOSE_DOCS else None,
        redoc_url=None,
        # The schema lists every endpoint; it is API documentation too.
        openapi_url="/openapi.json" if config.EXPOSE_DOCS else None,
    )

    app.state.db_path = Path(db_path or config.DB_PATH)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    def apply_security_headers(response: Response, path: str) -> Response:
        """Attach the same disclosure controls to successes and errors."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            f"script-src 'self' {script_hashes}; connect-src 'self' {' '.join(origins)}; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if config.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    @app.middleware("http")
    async def secure_responses(request, call_next):
        """Enforce proxy authentication and conservative browser policy."""
        public = request.url.path == "/api/health"
        if config.AUTH_MODE == "proxy" and not public:
            supplied = request.headers.get("X-GBD-Proxy-Secret", "")
            user = request.headers.get(config.AUTH_USER_HEADER, "").strip()
            if not user or not hmac.compare_digest(supplied, config.PROXY_SECRET):
                return apply_security_headers(
                    JSONResponse(
                        {"detail": "Authentication required"},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    ),
                    request.url.path,
                )
        response = await call_next(request)
        return apply_security_headers(response, request.url.path)

    # The dashboard is same-origin and needs no CORS at all, and notebooks, R
    # and curl are not browsers, so CORS never applies to them either. It is
    # only for a browser app on another site, and then only for the origins
    # named in GBD_CORS_ORIGINS -- never a wildcard by default.
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET"],
            allow_headers=["*"],
        )

    app.include_router(router)

    # Mounted LAST and at "/": FastAPI matches routes in declaration order, so
    # every /api/... route above resolves before this catch-all is reached.
    # html=True makes StaticFiles serve index.html for "/".
    if config.STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="dashboard")

    return app


# The instance uvicorn imports: `uvicorn app.main:app`.
app = create_app()
