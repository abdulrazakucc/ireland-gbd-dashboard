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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.routes import router

__version__ = "1.0.0"

DESCRIPTION = """
Global Burden of Disease indicators for Ireland, served live from a local
database built by the ETL in `etl/`.

Maintained by the School of Public Health, University College Cork.
Principal Investigator: Dr. Zubair Kabir.
"""


def create_app() -> FastAPI:
    """Build and return the application.

    A factory rather than a module-level singleton, so the test-suite can
    construct a fresh instance against a temporary database.
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

    # The dashboard is same-origin, so it needs no CORS at all. This is here
    # only so other researchers can query the API from their own tools --
    # notebooks, R, a separate frontend. Reads only: no cookies, no auth, and
    # no write routes exist to expose.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(router)

    # Mounted LAST and at "/": FastAPI matches routes in declaration order, so
    # every /api/... route above resolves before this catch-all is reached.
    # html=True makes StaticFiles serve index.html for "/".
    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="dashboard")

    return app


# The instance uvicorn imports: `uvicorn app.main:app`.
app = create_app()
