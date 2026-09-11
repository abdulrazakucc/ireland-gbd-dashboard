"""
The JSON API.

Every route is a thin HTTP layer over :mod:`app.queries`. All routes live under
``/api`` so the frontend, which is served from ``/``, can never collide with
them.

Dimension filters (``release, measure, metric, location, sex, age, cause,
risk, year_from, year_to``) mean the same thing on every route that takes
them. Values are matched exactly as they appear in ``/api/dimensions``.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app import figures, gbd, queries
from app.db import DatabaseNotInitialised
from app.queries import AmbiguousSelection, Filters
from app.schemas import (
    Dimensions,
    Estimates,
    Health,
    Meta,
    Ranked,
    RankedOption,
    SeriesInfo,
    Trend,
)

router = APIRouter(prefix="/api", tags=["gbd"])

EXPORT_COLUMNS = [
    "release", "measure", "metric", "location", "sex", "age", "cause", "risk",
    "year", "value", "lower", "upper",
]  # fmt: skip


def get_db_path(request: Request) -> Path:
    return request.app.state.db_path


DbPath = Annotated[Path, Depends(get_db_path)]


def selection(
    release: str | None = Query(None, description="e.g. 'GBD 2023'"),
    measure: str | None = Query(None, description="e.g. 'Deaths'"),
    metric: str | None = Query(None, description="'Number', 'Rate' or 'Percent'"),
    location: str | None = Query(None),
    sex: str | None = Query(None, description="e.g. 'Both'"),
    age: str | None = Query(None, description="e.g. 'Age-standardized'"),
    cause: str | None = Query(None, description="A cause; send it empty for rows with no cause"),
    risk: str | None = Query(None, description="A risk; send it empty for rows with no risk"),
    year_from: int | None = Query(None, ge=1950, le=2100, description="First year, inclusive"),
    year_to: int | None = Query(None, ge=1950, le=2100, description="Last year, inclusive"),
) -> Filters:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(status_code=422, detail="year_from must not be after year_to")
    return Filters(release, measure, metric, location, sex, age, cause, risk, year_from, year_to)


Selection = Annotated[Filters, Depends(selection)]
SeriesParam = Annotated[str | None, Query(description="A series_id from /api/series")]


def _read(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a query, turning operator and selection problems into clear HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except DatabaseNotInitialised as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AmbiguousSelection as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "The selection matches more than one; set these dimensions.",
                "varying": exc.varying,
            },
        ) from exc


def _series_or_404(
    db: Path, series: str | None, filters: Filters, forecast_years: int = 0
) -> dict[str, Any]:
    """The series named by id, or by a dimension selection that identifies exactly one."""
    if series is None:
        series = _read(
            queries.resolve_series,
            db,
            Filters(**{**filters.__dict__, "year_from": None, "year_to": None}),
        )
    data = series and _read(
        queries.fetch_series, db, series, filters.year_from, filters.year_to, forecast_years
    )
    if not data:
        raise HTTPException(status_code=404, detail="No estimates for that series and year range")
    return data


def _attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/health", response_model=Health, summary="Liveness check")
def health() -> dict:
    """Return OK if the process is up. Used by Docker and by `make smoke`."""
    return {"status": "ok"}


@router.get("/meta", response_model=Meta, summary="Dataset provenance")
def meta(db: DbPath) -> dict:
    """The GBD release, import date, de-identified provenance, and citation."""
    return _read(queries.fetch_meta, db)


@router.get("/dimensions", response_model=Dimensions, summary="Values available per dimension")
def dimensions(db: DbPath, filters: Selection) -> dict:
    """Distinct values of every dimension among the rows the filters match."""
    return _read(queries.list_dimensions, db, filters)


@router.get("/series", response_model=list[SeriesInfo], summary="Series catalogue")
def series(db: DbPath, filters: Selection) -> list[dict]:
    """Every series (all dimensions but year) and the years it covers. Drives the dropdowns."""
    return _read(queries.list_series, db, filters)


@router.get("/estimates", response_model=Estimates, summary="Filtered estimates")
def estimates(
    db: DbPath,
    filters: Selection,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
) -> dict:
    """Flat rows with uncertainty intervals, in a stable order, paged."""
    total, rows = _read(queries.fetch_estimates, db, filters, limit=limit, offset=offset)
    return {"total": total, "limit": limit, "offset": offset, "rows": rows}


@router.get("/trend", response_model=Trend, summary="One series over time")
def trend(
    db: DbPath,
    filters: Selection,
    series: SeriesParam = None,
    forecast_years: int = Query(0, ge=0, le=10, description="Years to project; 0 disables"),
) -> dict:
    """A series by ``series`` id, or by dimension filters that identify exactly one.

    Returns 409, listing the dimensions that still vary, when the filters match
    several series.
    """
    return _series_or_404(db, series, filters, forecast_years)


@router.get("/ranked/options", response_model=list[RankedOption], summary="Rankable selections")
def ranked_options(
    db: DbPath,
    type: Literal["causes", "risks"] | None = Query(None, description="'causes' or 'risks'"),
) -> list[dict]:
    """Every combination of dimensions and year that a ranking can be drawn for."""
    return _read(queries.ranked_options, db, type)


@router.get("/ranked", response_model=Ranked, summary="Leading causes or risks")
def ranked(
    db: DbPath,
    type: Literal["causes", "risks"] = Query(description="'causes' or 'risks'"),
    release: str | None = Query(None),
    measure: str | None = Query(None),
    metric: str | None = Query(None),
    location: str | None = Query(None),
    sex: str | None = Query(None),
    age: str | None = Query(None),
    year: int | None = Query(None, description="Default: the latest year available"),
    forecast_years: int = Query(0, ge=0, le=10, description="Years to project; 0 disables"),
) -> dict:
    """Causes (excluding the 'All causes' total) or risks, highest value first."""
    filters = Filters(release, measure, metric, location, sex, age)
    data = _read(queries.fetch_ranked, db, type, filters, year, forecast_years)
    if not data:
        raise HTTPException(status_code=404, detail="Nothing to rank for that selection")
    return data


@router.get(
    "/export.csv",
    summary="Download estimates as CSV",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV download"}},
)
def export_csv(
    db: DbPath,
    filters: Selection,
    series: SeriesParam = None,
    forecast_years: int = Query(0, ge=0, le=10, description="Years to project; 0 disables"),
) -> Response:
    """Every dimension, value and interval, optionally followed by projected rows."""
    total, rows = _read(queries.fetch_estimates, db, filters, series_id=series)
    if not total:
        raise HTTPException(status_code=404, detail="No estimates for that selection")

    fieldnames = EXPORT_COLUMNS
    data = None
    if forecast_years:
        data = _series_or_404(db, series, filters, forecast_years)
        fieldnames = [*EXPORT_COLUMNS, "record_type", "forecast_method"]
        for row in rows:
            row.update(record_type="observed", forecast_method="")
        point_columns = {"year", "value", "lower", "upper"}
        dimensions = {key: data.get(key) for key in EXPORT_COLUMNS if key not in point_columns}
        rows.extend(
            {
                **dimensions,
                **point,
                "record_type": "forecast",
                "forecast_method": data["forecast_info"]["model"],
            }
            for point in data["forecast"]
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    if series:
        data = data or _series_or_404(db, series, Filters())
        filename = gbd.download_name(data, "csv")
    else:
        filename = f"gbd_{gbd.slugify(rows[0]['release'])}_estimates.csv"
    return Response(buffer.getvalue(), media_type="text/csv", headers=_attachment(filename))


def _figure(
    db: Path,
    series: str | None,
    filters: Filters,
    fmt: Literal["png", "pdf"],
    forecast_years: int = 0,
) -> Response:
    data = _series_or_404(db, series, filters, forecast_years)
    body = figures.render_series(data, _read(queries.fetch_meta, db), fmt)
    return Response(
        body, media_type=figures.MEDIA_TYPES[fmt], headers=_attachment(gbd.download_name(data, fmt))
    )


@router.get(
    "/figure.png",
    summary="Download a series as a PNG figure",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}, "description": "PNG figure"}},
)
def figure_png(
    db: DbPath,
    filters: Selection,
    series: SeriesParam = None,
    forecast_years: int = Query(0, ge=0, le=10),
) -> Response:
    """A citation-stamped chart with the uncertainty band, ready for slides."""
    return _figure(db, series, filters, "png", forecast_years)


@router.get(
    "/figure.pdf",
    summary="Download a series as a PDF figure",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "PDF figure"}},
)
def figure_pdf(
    db: DbPath,
    filters: Selection,
    series: SeriesParam = None,
    forecast_years: int = Query(0, ge=0, le=10),
) -> Response:
    """The same figure as a vector PDF, for reports and print."""
    return _figure(db, series, filters, "pdf", forecast_years)
