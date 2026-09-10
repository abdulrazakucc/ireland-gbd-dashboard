"""
Application configuration: every filesystem path and runtime setting, resolved
once, in one place.

Nothing else in this codebase works out where a file lives by walking
``__file__``. Modules import the constants they need from here, which means:

* there is a single place to look when you want to know where the database is;
* every path can be overridden with an environment variable, which is how the
  Docker image and the test-suite point the app at a different location
  without editing any code.

Environment variables (all optional -- see ``.env.example``):

======================  ======================================================
``GBD_DATA_DIR``        Directory holding the CSVs and the SQLite database.
                        Default: ``<repo>/data``
``GBD_DB_PATH``         The SQLite database file itself.
                        Default: ``<GBD_DATA_DIR>/gbd.db``
``GBD_STATIC_DIR``      Directory of frontend files served at ``/``.
                        Default: ``<repo>/static``
``GBD_ROUND``           Release recorded against an import when neither the
                        command line nor the filename names one.
                        Default: ``GBD 2023``
``GBD_CORS_ORIGINS``    Comma-separated origins allowed to call the API from
                        a browser on another site. Default: none.
======================  ======================================================
"""

from __future__ import annotations

import os
from pathlib import Path

# The repository root: this file is <root>/app/config.py.
ROOT_DIR = Path(__file__).resolve().parent.parent


def _dir_from_env(var: str, default: Path) -> Path:
    """Return the path in ``var`` if it is set and non-empty, else ``default``."""
    value = os.environ.get(var, "").strip()
    return Path(value).expanduser() if value else default


def _list_from_env(var: str) -> list[str]:
    """Return the comma-separated values in ``var``, ignoring blanks."""
    return [item.strip() for item in os.environ.get(var, "").split(",") if item.strip()]


DATA_DIR: Path = _dir_from_env("GBD_DATA_DIR", ROOT_DIR / "data")
DB_PATH: Path = _dir_from_env("GBD_DB_PATH", DATA_DIR / "gbd.db")
STATIC_DIR: Path = _dir_from_env("GBD_STATIC_DIR", ROOT_DIR / "static")

# Where a researcher drops a freshly downloaded GBD Results Tool export.
INCOMING_DIR: Path = DATA_DIR / "incoming"

# The bundled prototype data, in the same long format as a real GBD export so
# that it goes through exactly the same importer and validation.
SEED_CSV: Path = DATA_DIR / "gbd_seed.csv"

# Recorded against every imported row so a served value can always be traced
# back to the GBD release it came from.
GBD_ROUND: str = os.environ.get("GBD_ROUND", "GBD 2023")

# Browser origins allowed to call the API cross-site. Empty by default: the
# dashboard is served from the same origin as the API and needs no CORS, and
# notebooks, R and curl are not browsers, so CORS never applies to them.
CORS_ORIGINS: list[str] = _list_from_env("GBD_CORS_ORIGINS")
