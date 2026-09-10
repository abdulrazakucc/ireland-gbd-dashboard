"""
Ireland Health Evidence -- UCC School of Public Health.

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

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config
from app.routes import router

__version__ = "2.0.0"

DESCRIPTION = """
Global Burden of Disease estimates for Ireland, served live from a local
database built by the ETL in `etl/`. Every estimate keeps its release, measure,
metric, location, sex, age, cause, risk, year and 95% uncertainty interval.

Start from `/api/series` (what exists) or `/api/dimensions` (which values
exist), then read a series with `/api/trend`, a ranking with `/api/ranked`,
or rows with `/api/estimates`; download with `/api/export.csv`,
`/api/figure.png` and `/api/figure.pdf`.

Maintained by the School of Public Health, University College Cork.
Principal Investigator: Dr. Zubair Kabir.
"""


def create_app(db_path: Path | None = None, cors_origins: list[str] | None = None) -> FastAPI:
    """Build and return the application.

    A factory rather than a module-level singleton, so the test-suite can
    construct a fresh instance against a temporary database.

    Args:
        db_path: The database to serve. Default: ``config.DB_PATH``.
        cors_origins: Browser origins allowed to call the API cross-site.
            Default: ``GBD_CORS_ORIGINS``, which is empty unless configured.
    """
    app = FastAPI(
        title="Ireland Health Evidence API",
        description=DESCRIPTION,
        version=__version__,
        contact={
            "name": "Dr. Zubair Kabir, School of Public Health, UCC",
            "url": "https://research.ucc.ie/en/persons/zubair-kabir/",
        },
    )

    app.state.db_path = Path(db_path or config.DB_PATH)

    # The dashboard is same-origin and needs no CORS at all, and notebooks, R
    # and curl are not browsers, so CORS never applies to them either. It is
    # only for a browser app on another site, and then only for the origins
    # named in GBD_CORS_ORIGINS -- never a wildcard by default.
    origins = config.CORS_ORIGINS if cors_origins is None else cors_origins
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
