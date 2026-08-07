"""
Response models for the API.

These are Pydantic models, so they do three jobs at once: they document the
shape of every response in the generated OpenAPI schema at ``/docs``, they
give the frontend a contract that cannot silently drift, and they fail loudly
in tests if a query starts returning a different shape.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Indicator(BaseModel):
    """One selectable trend indicator."""

    indicator_id: str = Field(description="Stable short ID, e.g. 'tobacco_sev'")
    indicator_label: str = Field(description="Human-readable name")
    unit: str = Field(description="Unit of the values, e.g. 'percent'")


class TrendPoint(BaseModel):
    """A single year's value within a trend series."""

    year: int
    value: float


class Trend(BaseModel):
    """A time series for one indicator, one location, one sex."""

    indicator: str
    label: str
    unit: str
    location: str
    sex: str
    series: list[TrendPoint] = Field(description="Ordered by year, ascending")


class RankedItem(BaseModel):
    """One bar in a ranked chart."""

    label: str
    value: float
    unit: str


class Ranked(BaseModel):
    """Leading causes or risk factors for one location and year."""

    type: str = Field(description="'causes' or 'risks'")
    location: str
    year: int
    items: list[RankedItem] = Field(description="Ordered by value, descending")


class Health(BaseModel):
    """Liveness response."""

    status: str
