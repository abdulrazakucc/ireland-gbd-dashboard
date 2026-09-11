"""
Downloadable figures: one series as a PNG or PDF, with its GBD context attached.

A figure leaves the dashboard and gets pasted into slides and reports, where
nobody can see which selection produced it. So everything a reader needs to
interpret and cite it is drawn *on* the figure -- release, every dimension,
the uncertainty interval, the IHME citation, de-identified provenance and import date
-- and repeated in the file's own metadata.

Rendering uses matplotlib's object-oriented API and never ``pyplot``:
``pyplot`` keeps global state and is not safe on the thread-pool FastAPI runs
sync endpoints on. A bare ``Figure`` has no shared state at all.
"""

from __future__ import annotations

import io
import math
import textwrap
from datetime import UTC, datetime
from typing import Any, Literal

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator

MEDIA_TYPES = {"png": "image/png", "pdf": "application/pdf"}

NAVY, LINE, TEXT, MUTED, GRID, ALERT = (
    "#0f2942",
    "#2a78d6",
    "#14181d",
    "#4d5561",
    "#e7e9ee",
    "#b3261e",
)
PUBLISHER = "Global Health Evidence, School of Public Health, University College Cork"


def format_number(value: float) -> str:
    """Match the dashboard: fewer decimals as numbers grow."""
    magnitude = abs(value)
    if magnitude >= 1000:
        return f"{value:,.0f}"
    text = f"{value:,.1f}" if magnitude >= 100 else f"{value:,.2f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def describe(series: dict[str, Any]) -> str:
    """The selection in one line: every dimension that is not already the title."""
    years = [p["year"] for p in series["series"]]
    span = f"{years[0]}–{years[-1]}" if years[0] != years[-1] else str(years[0])
    parts = [
        series["measure"] if series["measure"] != series["title"] else None,
        f"{series['metric']} ({series['unit']})"
        if series["unit"].lower() != series["metric"].lower()
        else series["metric"],
        series["age"],
        series["sex"],
        series["location"],
        span,
    ]
    return " · ".join(p for p in parts if p)


def render_series(
    series: dict[str, Any], meta: dict[str, Any], fmt: Literal["png", "pdf"]
) -> bytes:
    """Render one series (as returned by ``queries.fetch_series``) to PNG or PDF bytes."""
    if fmt not in MEDIA_TYPES:
        raise ValueError(f"Unsupported figure format: {fmt}")

    scale = series["display_scale"]
    points = series["series"]
    years = [p["year"] for p in points]
    values = [p["value"] * scale for p in points]
    # NaN where a year has no interval: matplotlib leaves a gap rather than
    # drawing a band nobody published.
    lower = [p["lower"] * scale if p["lower"] is not None else math.nan for p in points]
    upper = [p["upper"] * scale if p["upper"] is not None else math.nan for p in points]
    projected = series.get("forecast", [])
    forecast_years = [p["year"] for p in projected]
    forecast_values = [p["value"] * scale for p in projected]
    forecast_lower = [p["lower"] * scale for p in projected]
    forecast_upper = [p["upper"] * scale for p in projected]
    subtitle = describe(series)
    citation = meta["citation"]
    generated = datetime.now(UTC).strftime("%Y-%m-%d")

    fig = Figure(figsize=(8, 5.6), dpi=150, facecolor="white")
    fig.text(0.07, 0.945, series["title"], fontsize=14, fontweight="bold", color=NAVY, va="top")
    fig.text(0.07, 0.885, subtitle, fontsize=9, color=MUTED, va="top")
    fig.text(
        0.93,
        0.945,
        series["release"],
        fontsize=9,
        fontweight="bold",
        color=NAVY,
        ha="right",
        va="top",
    )

    ax = fig.add_axes((0.09, 0.285, 0.86, 0.54))
    if series["has_uncertainty"]:
        ax.fill_between(
            years,
            lower,
            upper,
            color=LINE,
            alpha=0.18,
            linewidth=0,
            label="95% uncertainty interval",
        )
    ax.plot(years, values, color=LINE, linewidth=2, marker="o", markersize=4, label="Estimate")
    if projected:
        forecast_color = "#08785a"
        ax.fill_between(
            forecast_years,
            forecast_lower,
            forecast_upper,
            color=forecast_color,
            alpha=0.13,
            linewidth=0,
            label="Approx. 95% prediction interval",
        )
        ax.plot(
            [years[-1], *forecast_years],
            [values[-1], *forecast_values],
            color=forecast_color,
            linewidth=2,
            linestyle="--",
            marker="o",
            markersize=4,
            label="Exploratory forecast",
        )
    ax.annotate(
        format_number(values[-1]),
        (years[-1], values[-1]),
        xytext=(7, 0),
        textcoords="offset points",
        va="center",
        fontsize=9,
        fontweight="bold",
        color=TEXT,
    )

    ax.set_xlabel("Year", fontsize=9, color=MUTED)
    ax.set_ylabel(series["unit"], fontsize=9, color=MUTED)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: format_number(v)))
    if len(set(years)) == 1:
        ax.set_xlim(years[0] - 1, years[0] + 1)
    ax.margins(x=0.06)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#cfd4dc")
    if series["has_uncertainty"] or projected:
        ax.legend(loc="best", frameon=False, fontsize=8.5)

    files = ", ".join(f["label"] for f in meta["source_files"]) or "approved source"
    dataset = (
        f"Dataset: {meta['source']} ({files}), {meta['release']}, "
        f"imported {meta['imported_at'][:10]}."
    )
    footer = [
        *textwrap.wrap(f"Source: {citation}", 150),
        *textwrap.wrap(dataset, 150),
        f"Figure: {PUBLISHER}. Generated {generated}.",
    ]
    if projected:
        footer.append(
            "Forecast: linear least-squares trend; exploratory only, not a clinical or "
            "epidemiological prediction."
        )
    fig.text(
        0.07, 0.035, "\n".join(footer), fontsize=6.6, color=MUTED, va="bottom", linespacing=1.5
    )
    if meta.get("prototype"):
        fig.text(
            0.07,
            0.035 + 0.026 * (len(footer) + 0.3),
            meta["notice"],
            fontsize=7.5,
            fontweight="bold",
            color=ALERT,
            va="bottom",
        )

    buffer = io.BytesIO()
    if fmt == "png":
        metadata = {
            "Title": series["title"],
            "Description": subtitle,
            "Source": citation,
            "Comment": dataset
            + (
                " Forecast: exploratory linear trend; not a clinical or epidemiological prediction."
                if projected
                else ""
            ),
            "Software": PUBLISHER,
        }
        if meta.get("prototype"):
            metadata["Disclaimer"] = meta["notice"]
    else:
        metadata = {
            "Title": series["title"],
            "Subject": f"{subtitle}. {citation}",
            "Keywords": f"{meta['release']}; {series['measure']}; {series['location']}",
            "Author": PUBLISHER,
            "Creator": PUBLISHER,
        }
    fig.savefig(buffer, format=fmt, metadata=metadata)
    return buffer.getvalue()
