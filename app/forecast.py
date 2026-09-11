"""Transparent, dependency-free forecasts for exploratory analysis.

Forecasts are deliberately calculated on request and are never written back to
the source dataset.  A straight-line least-squares model is intentionally used:
it is reproducible, inspectable, and honest about the limited information in an
annual aggregate series.  These projections are analytical aids, not clinical
predictions or substitutes for an epidemiological model.
"""

from __future__ import annotations

import math
from typing import Any

MIN_POINTS = 3
MAX_TRAINING_POINTS = 15
MODEL_NAME = "Linear trend (ordinary least squares)"


def forecast_points(
    points: list[dict[str, Any]], horizon: int, metric: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project ``horizon`` annual points and return them with model metadata.

    The interval is an approximate 95% prediction interval.  It includes both
    residual uncertainty and uncertainty in the fitted mean.  Non-negative
    source series remain non-negative; percentages are additionally bounded at
    one because they are stored as proportions.
    """
    usable = sorted(
        ({"year": int(p["year"]), "value": float(p["value"])} for p in points),
        key=lambda p: p["year"],
    )[-MAX_TRAINING_POINTS:]
    years = [p["year"] for p in usable]
    values = [p["value"] for p in usable]
    metadata: dict[str, Any] = {
        "model": MODEL_NAME,
        "horizon": horizon,
        "training_points": len(usable),
        "training_year_min": min(years) if years else None,
        "training_year_max": max(years) if years else None,
        "confidence_level": 0.95,
        "status": "available",
        "note": (
            "Exploratory projection from the recent observed trend; not a clinical or "
            "epidemiological prediction."
        ),
    }
    if len(set(years)) < MIN_POINTS:
        metadata.update(
            status="unavailable",
            note=f"At least {MIN_POINTS} distinct annual observations are required.",
        )
        return [], metadata

    n = len(years)
    x_mean = sum(years) / n
    y_mean = sum(values) / n
    ss_x = sum((x - x_mean) ** 2 for x in years)
    if ss_x == 0:
        metadata.update(status="unavailable", note="The observations do not span enough years.")
        return [], metadata
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(years, values, strict=True)) / ss_x
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(years, values, strict=True)]
    residual_se = math.sqrt(sum(r * r for r in residuals) / max(n - 2, 1))
    nonnegative = min(values) >= 0
    percent = metric.strip().lower() == "percent"

    forecasts = []
    last_year = max(years)
    for year in range(last_year + 1, last_year + horizon + 1):
        estimate = intercept + slope * year
        prediction_se = residual_se * math.sqrt(1 + 1 / n + (year - x_mean) ** 2 / ss_x)
        lower, upper = estimate - 1.96 * prediction_se, estimate + 1.96 * prediction_se
        if nonnegative:
            estimate, lower, upper = max(0.0, estimate), max(0.0, lower), max(0.0, upper)
        if percent:
            estimate, lower, upper = min(1.0, estimate), min(1.0, lower), min(1.0, upper)
        forecasts.append({"year": year, "value": estimate, "lower": lower, "upper": upper})
    return forecasts, metadata
