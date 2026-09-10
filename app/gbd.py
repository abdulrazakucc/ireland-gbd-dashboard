"""
GBD domain rules shared by the API, the figure renderer and the importer.

Kept in one place so that a figure, a chart and a CSV can never disagree about
what a metric means or how a release is cited.
"""

from __future__ import annotations

import re

# `meta.source` for the bundled prototype data. Anything carrying this label is
# marked as not citable wherever it is exported.
SEED_SOURCE = "Prototype seed data"
PROTOTYPE_NOTICE = (
    "Prototype seed data gathered during development — not a verified IHME export. "
    "Do not cite these figures."
)

# IHME's Results Tool reports Rate per 100,000 population, and Percent as a
# proportion (0.12 = 12%). The importer enforces the proportion convention, so
# scaling Percent by 100 for display is safe rather than a guess.
_UNITS = {"rate": "per 100,000", "percent": "%", "years": "years", "number": "number"}


def unit_for(metric: str) -> str:
    """Human-readable unit for a GBD metric, e.g. ``'Rate'`` -> ``'per 100,000'``."""
    return _UNITS.get(metric.strip().lower(), metric)


def display_scale(metric: str) -> float:
    """Factor that turns a stored value into the number a reader expects to see."""
    return 100.0 if metric.strip().lower() == "percent" else 1.0


def series_title(measure: str, cause: str | None, risk: str | None) -> str:
    """Name a series by what it is about: risk -> cause, a cause, a risk, or the measure."""
    if risk and cause:
        return f"{risk} → {cause}"
    return risk or cause or measure


def citation(release: str) -> str:
    """The IHME attribution for a release.

    The publication year is deliberately omitted: it differs per round and is
    not recorded in an export, and a wrong year in a citation is worse than none.
    """
    match = re.search(r"GBD\s*(\d{4})", release, re.IGNORECASE)
    study = f"Global Burden of Disease Study {match.group(1)} ({release})" if match else release
    return (
        f"Global Burden of Disease Collaborative Network. {study} Results. "
        "Seattle, United States: Institute for Health Metrics and Evaluation (IHME). "
        "Available from https://vizhub.healthdata.org/gbd-results/. "
        "Used under IHME's Free-to-Use Data Terms."
    )


def slugify(text: str) -> str:
    """A filename-safe form of ``text``: 'HALE (Healthy life expectancy)' -> 'hale-healthy-...'."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "gbd"


def download_name(series: dict, extension: str) -> str:
    """Filename for a downloaded series: what it is, which release, and a short id."""
    parts = [series["title"], series["measure"], series["release"]]
    stem = "_".join(dict.fromkeys(slugify(p) for p in parts))
    return f"{stem}_{series['series_id'][:8]}.{extension}"
