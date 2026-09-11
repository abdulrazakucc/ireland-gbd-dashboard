"""
Response models for the API.

These are Pydantic models, so they do three jobs at once: they document the
shape of every response in the generated OpenAPI schema at ``/docs``, they
give the frontend a contract that cannot silently drift, and they fail loudly
in tests if a query starts returning a different shape.

Throughout, ``cause`` and ``risk`` are ``null`` where the dimension does not
apply (life expectancy has neither; an exposure has a risk but no cause), and
``lower``/``upper`` are ``null`` where the source gave no uncertainty interval.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Health(BaseModel):
    """Liveness response."""

    status: str


class SourceFileInfo(BaseModel):
    label: str = Field(description="Non-identifying source label")
    row_count: int


class Meta(BaseModel):
    """Provenance of the dataset currently being served."""

    release: str = Field(description="GBD release, e.g. 'GBD 2023'")
    source: str = Field(description="Where the data came from")
    imported_at: str = Field(description="When this dataset was built (ISO 8601, UTC)")
    row_count: int
    series_count: int
    year_min: int | None
    year_max: int | None
    schema_version: int
    source_files: list[SourceFileInfo]
    citation: str = Field(description="IHME attribution for this release")
    prototype: bool = Field(description="True for the bundled seed data, which is not citable")
    notice: str | None


class SeriesDims(BaseModel):
    """Every dimension that identifies a series, plus how to display its values."""

    release: str
    measure: str
    metric: str
    location: str
    sex: str
    age: str
    cause: str | None
    risk: str | None
    title: str = Field(description="What the series is about: risk → cause, cause, risk or measure")
    unit: str = Field(description="Display unit for the metric, e.g. 'per 100,000'")
    display_scale: float = Field(description="Multiply stored values by this for display")


class SeriesInfo(SeriesDims):
    """One catalogue entry: a series and the years it covers."""

    series_id: str
    year_min: int
    year_max: int
    years: list[int]
    has_uncertainty: bool


class Point(BaseModel):
    year: int
    value: float
    lower: float | None
    upper: float | None


class ForecastInfo(BaseModel):
    """Method and fitness information attached to every requested forecast."""

    model: str
    horizon: int
    training_points: int
    training_year_min: int | None
    training_year_max: int | None
    confidence_level: float
    status: str
    note: str


class Trend(SeriesDims):
    """One series over time, with uncertainty intervals."""

    series_id: str
    has_uncertainty: bool
    series: list[Point] = Field(description="Ordered by year, ascending")
    forecast: list[Point] = Field(default_factory=list, description="Projected annual points")
    forecast_info: ForecastInfo | None = None


class Dimensions(BaseModel):
    """Distinct values available for each dimension, given any filters applied."""

    release: list[str | None]
    measure: list[str | None]
    metric: list[str | None]
    location: list[str | None]
    sex: list[str | None]
    age: list[str | None]
    cause: list[str | None]
    risk: list[str | None]
    year_min: int | None
    year_max: int | None


class Estimate(BaseModel):
    release: str
    measure: str
    metric: str
    location: str
    sex: str
    age: str
    cause: str | None
    risk: str | None
    year: int
    value: float
    lower: float | None
    upper: float | None


class Estimates(BaseModel):
    total: int = Field(description="Rows matching the filters, before paging")
    limit: int
    offset: int
    rows: list[Estimate]


class RankedItem(BaseModel):
    """One bar in a ranked chart."""

    label: str
    value: float
    lower: float | None
    upper: float | None
    series_id: str


class RankedOption(BaseModel):
    """One combination a ranking can be drawn for."""

    type: str
    release: str
    measure: str
    metric: str
    location: str
    sex: str
    age: str
    year: int
    unit: str
    display_scale: float


class Ranked(RankedOption):
    """Leading causes or risk factors for one combination, highest value first."""

    items: list[RankedItem]
    forecast_year: int | None = None
    forecast_items: list[RankedItem] = Field(default_factory=list)
    forecast_info: ForecastInfo | None = None
