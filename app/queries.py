"""
Every read the application makes, as plain functions over a database path.

The HTTP routes, the figure renderer, the static-snapshot build and the
importer's verification step all call these. So the question "what does the
API return for this selection?" has exactly one answer, wherever it is asked.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from app import gbd
from app.db import query

DIMENSIONS = ("release", "measure", "metric", "location", "sex", "age", "cause", "risk")
SERIES_COLUMNS = ", ".join(DIMENSIONS)

# Which rows a ranking may compare. "All causes" is a total, not a rival cause,
# and a risk is ranked on its all-cause burden (or its exposure, with no cause).
RANK_RULES = {
    "causes": "risk = '' AND cause NOT IN ('', 'All causes')",
    "risks": "risk <> '' AND cause IN ('', 'All causes')",
}
RANK_LABEL = {"causes": "cause", "risks": "risk"}


class AmbiguousSelection(LookupError):
    """A selection matched more than one series or ranking; say which dimensions vary."""

    def __init__(self, varying: dict[str, list[Any]]) -> None:
        self.varying = varying
        super().__init__("Selection is ambiguous; narrow it with: " + ", ".join(varying))


@dataclass(frozen=True)
class Filters:
    """Optional equality filters on every dimension, plus an inclusive year range.

    ``None`` means "do not filter". For cause and risk, ``""`` is a real value
    meaning "this dimension does not apply", e.g. ``cause=""`` selects life
    expectancy and exposure series rather than every cause.
    """

    release: str | None = None
    measure: str | None = None
    metric: str | None = None
    location: str | None = None
    sex: str | None = None
    age: str | None = None
    cause: str | None = None
    risk: str | None = None
    year_from: int | None = None
    year_to: int | None = None

    def where(self, *extra: str) -> tuple[str, list[Any]]:
        clauses, params = list(extra), []
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                continue
            if f.name == "year_from":
                clauses.append("year >= ?")
            elif f.name == "year_to":
                clauses.append("year <= ?")
            else:
                clauses.append(f"{f.name} = ?")
            params.append(value)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _describe(row: dict[str, Any]) -> dict[str, Any]:
    """Blank cause/risk become null, and the display fields are attached."""
    row["cause"] = row.get("cause") or None
    row["risk"] = row.get("risk") or None
    row["title"] = gbd.series_title(row["measure"], row["cause"], row["risk"])
    row["unit"] = gbd.unit_for(row["metric"])
    row["display_scale"] = gbd.display_scale(row["metric"])
    return row


def fetch_meta(db_path: Path | None = None) -> dict[str, Any]:
    meta = {r["key"]: r["value"] for r in query("SELECT key, value FROM meta", db_path=db_path)}
    files = query(
        "SELECT filename, sha256, bytes, row_count FROM source_file ORDER BY rowid",
        db_path=db_path,
    )
    release = meta.get("release", "")
    prototype = meta.get("source") == gbd.SEED_SOURCE
    return {
        "release": release,
        "source": meta.get("source", ""),
        "imported_at": meta.get("imported_at", ""),
        "row_count": int(meta.get("row_count", 0)),
        "series_count": int(meta.get("series_count", 0)),
        "year_min": int(meta["year_min"]) if meta.get("year_min") else None,
        "year_max": int(meta["year_max"]) if meta.get("year_max") else None,
        "schema_version": int(meta.get("schema_version", 0)),
        "source_files": files,
        "citation": gbd.citation(release),
        "prototype": prototype,
        "notice": gbd.PROTOTYPE_NOTICE if prototype else None,
    }


def list_series(db_path: Path | None = None, filters: Filters | None = None) -> list[dict]:
    """The catalogue: one entry per series, with the years it covers."""
    where, params = (filters or Filters()).where()
    rows = query(
        f"SELECT series_id, {SERIES_COLUMNS}, MIN(year) AS year_min, MAX(year) AS year_max, "
        "group_concat(year) AS years, COUNT(lower) AS with_uncertainty "
        f"FROM gbd_estimate{where} GROUP BY series_id "
        "ORDER BY measure, cause, risk, metric, age, sex, location, release",
        params,
        db_path,
    )
    for row in rows:
        row["years"] = sorted(int(y) for y in row["years"].split(","))
        row["has_uncertainty"] = row.pop("with_uncertainty") > 0
        _describe(row)
    return rows


def resolve_series(db_path: Path | None, filters: Filters) -> str | None:
    """The one series a dimension selection names, or None; ambiguity is an error."""
    where, params = filters.where()
    rows = query(
        f"SELECT DISTINCT series_id, {SERIES_COLUMNS} FROM gbd_estimate{where}", params, db_path
    )
    if len(rows) > 1:
        raise AmbiguousSelection(_varying(rows, DIMENSIONS))
    return rows[0]["series_id"] if rows else None


def fetch_series(
    db_path: Path | None, series_id: str, year_from: int | None = None, year_to: int | None = None
) -> dict[str, Any] | None:
    """One series with its points and uncertainty intervals, or None."""
    where, params = Filters(year_from=year_from, year_to=year_to).where("series_id = ?")
    rows = query(
        f"SELECT {SERIES_COLUMNS}, year, value, lower, upper "
        f"FROM gbd_estimate{where} ORDER BY year",
        [series_id, *params],
        db_path,
    )
    if not rows:
        return None
    head = _describe({d: rows[0][d] for d in DIMENSIONS})
    return {
        "series_id": series_id,
        **head,
        "has_uncertainty": any(r["lower"] is not None for r in rows),
        "series": [{k: r[k] for k in ("year", "value", "lower", "upper")} for r in rows],
    }


def list_dimensions(db_path: Path | None = None, filters: Filters | None = None) -> dict[str, Any]:
    """Distinct values of every dimension among the rows a selection matches."""
    where, params = (filters or Filters()).where()
    result: dict[str, Any] = {}
    for dim in DIMENSIONS:
        values = query(
            f"SELECT DISTINCT {dim} AS v FROM gbd_estimate{where} ORDER BY v", params, db_path
        )
        result[dim] = [r["v"] or None for r in values]
    years = query(
        f"SELECT MIN(year) AS lo, MAX(year) AS hi FROM gbd_estimate{where}", params, db_path
    )
    result["year_min"], result["year_max"] = years[0]["lo"], years[0]["hi"]
    return result


def fetch_estimates(
    db_path: Path | None,
    filters: Filters,
    series_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[int, list[dict[str, Any]]]:
    """Flat rows for a selection, in a stable order, with the total before paging."""
    extra = ("series_id = ?",) if series_id else ()
    where, params = filters.where(*extra)
    params = [series_id, *params] if series_id else params
    total = query(f"SELECT COUNT(*) AS n FROM gbd_estimate{where}", params, db_path)[0]["n"]
    page = f" LIMIT {int(limit)} OFFSET {int(offset)}" if limit is not None else ""
    rows = query(
        f"SELECT {SERIES_COLUMNS}, year, value, lower, upper FROM gbd_estimate{where} "
        f"ORDER BY measure, cause, risk, metric, location, sex, age, release, year{page}",
        params,
        db_path,
    )
    for row in rows:
        row["cause"], row["risk"] = row["cause"] or None, row["risk"] or None
    return total, rows


def ranked_options(db_path: Path | None = None, rank_type: str | None = None) -> list[dict]:
    """Every (type, dimensions, year) combination a ranking can be drawn for."""
    options = []
    for kind, rule in RANK_RULES.items():
        if rank_type and kind != rank_type:
            continue
        combos = query(
            f"SELECT DISTINCT release, measure, metric, location, sex, age, year "
            f"FROM gbd_estimate WHERE {rule} ORDER BY measure, metric, age, sex, location, year",
            db_path=db_path,
        )
        for combo in combos:
            combo.update(
                type=kind,
                unit=gbd.unit_for(combo["metric"]),
                display_scale=gbd.display_scale(combo["metric"]),
            )
            options.append(combo)
    return options


def fetch_ranked(
    db_path: Path | None, rank_type: str, filters: Filters, year: int | None = None
) -> dict[str, Any] | None:
    """Items ranked high to low for one combination; the latest year unless one is given.

    Raises:
        AmbiguousSelection: the filters leave more than one measure, metric,
            age, sex, location or release to rank within.
    """
    rule = RANK_RULES[rank_type]
    dims = ("release", "measure", "metric", "location", "sex", "age")
    where, params = filters.where(rule)
    combos = query(f"SELECT DISTINCT {', '.join(dims)} FROM gbd_estimate{where}", params, db_path)
    if not combos:
        return None
    if len(combos) > 1:
        raise AmbiguousSelection(_varying(combos, dims))
    combo = combos[0]
    pinned = Filters(**combo)
    where, params = pinned.where(rule)
    if year is None:
        year = query(f"SELECT MAX(year) AS y FROM gbd_estimate{where}", params, db_path)[0]["y"]
    label = RANK_LABEL[rank_type]
    items = query(
        f"SELECT {label} AS label, value, lower, upper, series_id FROM gbd_estimate"
        f"{where} AND year = ? ORDER BY value DESC, label",
        [*params, year],
        db_path,
    )
    if not items:
        return None
    return {
        "type": rank_type,
        **combo,
        "year": year,
        "unit": gbd.unit_for(combo["metric"]),
        "display_scale": gbd.display_scale(combo["metric"]),
        "items": items,
    }


def _varying(rows: list[dict], dims: tuple[str, ...]) -> dict[str, list[Any]]:
    varying = {}
    for dim in dims:
        values = sorted({r[dim] for r in rows})
        if len(values) > 1:
            varying[dim] = [v or None for v in values]
    return varying
