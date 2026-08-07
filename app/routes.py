"""
The JSON API.

Every route is a thin read over the SQLite database the ETL builds. All routes
live under ``/api`` so the frontend, which is served from ``/``, can never
collide with them.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import DEFAULT_LOCATION
from app.db import DatabaseNotInitialised, query
from app.schemas import Health, Indicator, Ranked, Trend

router = APIRouter(prefix="/api", tags=["gbd"])


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query, converting a missing database into a 503.

    A missing database means the ETL has not run -- an operator problem with a
    known fix -- so the client gets a clear instruction instead of a 500.
    """
    try:
        return query(sql, params)
    except DatabaseNotInitialised as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/health", response_model=Health, summary="Liveness check")
def health() -> dict:
    """Return OK if the process is up. Used by Docker and by `make smoke`."""
    return {"status": "ok"}


@router.get("/meta", summary="Data provenance")
def meta() -> dict[str, str]:
    """Return the GBD round and source recorded by the last ETL run."""
    return {row["key"]: row["value"] for row in _query("SELECT key, value FROM meta")}


@router.get("/indicators", response_model=list[Indicator], summary="Available indicators")
def indicators() -> list[dict]:
    """List every trend indicator in the database, for the dropdown."""
    return _query(
        "SELECT DISTINCT indicator_id, indicator_label, unit "
        "FROM trend_indicator ORDER BY indicator_label"
    )


@router.get("/trend", response_model=Trend, summary="Time series for one indicator")
def trend(
    indicator: str = Query(description="An indicator_id from /api/indicators"),
    location: str = Query(default=DEFAULT_LOCATION),
    sex: str = Query(default="combined"),
) -> dict:
    """Return the full time series for one indicator, ordered by year."""
    rows = _query(
        "SELECT year, value, unit, indicator_label FROM trend_indicator "
        "WHERE indicator_id = ? AND location = ? AND sex = ? ORDER BY year",
        (indicator, location, sex),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for indicator '{indicator}'")
    return {
        "indicator": indicator,
        "label": rows[0]["indicator_label"],
        "unit": rows[0]["unit"],
        "location": location,
        "sex": sex,
        "series": [{"year": r["year"], "value": r["value"]} for r in rows],
    }


@router.get("/ranked", response_model=Ranked, summary="Leading causes or risks")
def ranked(
    type: str = Query(pattern="^(causes|risks)$", description="'causes' or 'risks'"),
    location: str = Query(default=DEFAULT_LOCATION),
    year: int = Query(default=2023),
) -> dict:
    """Return ranked causes or risk factors, highest value first."""
    rows = _query(
        "SELECT label, value, unit FROM ranked_indicator "
        "WHERE rank_type = ? AND location = ? AND year = ? ORDER BY value DESC",
        (type, location, year),
    )
    return {"type": type, "location": location, "year": year, "items": rows}


@router.get(
    "/export.csv",
    summary="Download one indicator as CSV",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV download"}},
)
def export_csv(
    indicator: str = Query(description="An indicator_id from /api/indicators"),
    location: str = Query(default=DEFAULT_LOCATION),
) -> StreamingResponse:
    """Return one indicator as CSV, so a value on screen can be cited and reused."""
    rows = _query(
        "SELECT indicator_id, indicator_label, location, sex, year, value, unit, gbd_round "
        "FROM trend_indicator WHERE indicator_id = ? AND location = ? ORDER BY year",
        (indicator, location),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for indicator '{indicator}'")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={indicator}.csv"},
    )
