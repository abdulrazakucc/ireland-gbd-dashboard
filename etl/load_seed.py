"""
ETL: build the SQLite database the API reads.

Two ingestion paths:

1. :func:`load_seed` -- load the bundled prototype CSVs in ``data/``. This is
   what runs automatically the first time you start the app, so the dashboard
   has something to show immediately.

2. :func:`ingest_gbd_export` -- the adapter for a **real** bulk CSV export from
   the IHME GBD Results Tool (https://vizhub.healthdata.org/gbd-results/).
   Point it at a downloaded export and it fills the same schema, so neither
   the API nor the dashboard changes when you move off the seed data.

Why there is no "fetch from IHME" function: IHME publishes GBD in annual
rounds as bulk downloads. There is no free real-time query API to call, so
re-running this script when a new round lands *is* the update mechanism.

Usage:

.. code-block:: console

    make seed                                        # the bundled seed data
    python -m etl.load_seed                          # the same thing
    python -m etl.load_seed --gbd-export data/incoming/IHME-GBD_2023_DATA.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path

# Allow `python etl/load_seed.py` as well as `python -m etl.load_seed` by
# putting the repository root on the import path when run as a bare script.
if __package__ in (None, ""):  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import (  # noqa: E402  (import must follow the path bootstrap)
    DB_PATH,
    GBD_ROUND,
    SEED_RANKED_CSV,
    SEED_TREND_CSV,
)

# Composite primary keys make every load idempotent: re-running the ETL
# replaces rows rather than duplicating them.
SCHEMA = """
CREATE TABLE IF NOT EXISTS trend_indicator (
    indicator_id    TEXT    NOT NULL,
    indicator_label TEXT    NOT NULL,
    location        TEXT    NOT NULL,
    sex             TEXT    NOT NULL,
    year            INTEGER NOT NULL,
    value           REAL    NOT NULL,
    unit            TEXT    NOT NULL,
    gbd_round       TEXT    NOT NULL,
    PRIMARY KEY (indicator_id, location, sex, year)
);

CREATE TABLE IF NOT EXISTS ranked_indicator (
    rank_type TEXT    NOT NULL,
    label     TEXT    NOT NULL,
    location  TEXT    NOT NULL,
    year      INTEGER NOT NULL,
    value     REAL    NOT NULL,
    unit      TEXT    NOT NULL,
    gbd_round TEXT    NOT NULL,
    PRIMARY KEY (rank_type, label, location, year)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

TREND_INSERT = (
    "INSERT OR REPLACE INTO trend_indicator "
    "(indicator_id, indicator_label, location, sex, year, value, unit, gbd_round) "
    "VALUES (?,?,?,?,?,?,?,?)"
)
RANKED_INSERT = (
    "INSERT OR REPLACE INTO ranked_indicator "
    "(rank_type, label, location, year, value, unit, gbd_round) "
    "VALUES (?,?,?,?,?,?,?)"
)


def get_conn() -> sqlite3.Connection:
    """Open the database, creating the file and schema if they do not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_seed() -> None:
    """Load the bundled prototype CSVs into the database."""
    conn = get_conn()
    cursor = conn.cursor()

    trend_rows = [
        (
            row["indicator_id"],
            row["indicator_label"],
            row["location"],
            row["sex"],
            int(row["year"]),
            float(row["value"]),
            row["unit"],
            row["gbd_round"],
        )
        for row in _read_csv(SEED_TREND_CSV)
    ]
    cursor.executemany(TREND_INSERT, trend_rows)
    print(f"Loaded {len(trend_rows)} trend rows.")

    ranked_rows = [
        (
            row["rank_type"],
            row["label"],
            row["location"],
            int(row["year"]),
            float(row["value"]),
            row["unit"],
            row["gbd_round"],
        )
        for row in _read_csv(SEED_RANKED_CSV)
    ]
    cursor.executemany(RANKED_INSERT, ranked_rows)
    print(f"Loaded {len(ranked_rows)} ranked rows.")

    _set_meta(cursor, "gbd_round", GBD_ROUND)
    _set_meta(cursor, "source", "seed_prototype_data")

    conn.commit()
    conn.close()


def _set_meta(cursor: sqlite3.Cursor, key: str, value: str) -> None:
    cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def _slugify(text: str) -> str:
    """Turn 'High body-mass index' into 'high_body_mass_index'."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def ingest_gbd_export(csv_path: str, indicator_map: dict[str, str] | None = None) -> int:
    """Ingest a real IHME GBD Results Tool bulk CSV export.

    The public export schema (as of GBD 2023) carries columns along the lines
    of ``measure_name, location_name, sex_name, age_name, cause_name /
    rei_name, metric_name, year, val, upper, lower``. This maps those onto the
    same tables :func:`load_seed` fills.

    Args:
        csv_path: Path to the downloaded export.
        indicator_map: Optional ``{source name: your short ID}`` mapping, e.g.
            ``{"Tobacco": "tobacco_sev"}``. **Recommended**: without it, names
            are slugified, so a wording change at IHME between rounds would
            silently create a *new* indicator ID and break the dashboard's
            saved selection. With it, your IDs stay stable across re-ingests.

    Returns:
        The number of rows ingested.
    """
    conn = get_conn()
    cursor = conn.cursor()
    ingested = 0

    with open(csv_path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row.get("cause_name") or row.get("rei_name") or row.get("indicator_name")
            if not name:
                continue

            indicator_id = (indicator_map or {}).get(name, _slugify(name))
            metric = (row.get("metric_name") or "").lower()
            unit = "percent" if metric == "percent" else (row.get("metric_name") or "value")

            try:
                cursor.execute(
                    TREND_INSERT,
                    (
                        indicator_id,
                        name,
                        row.get("location_name", "Ireland"),
                        (row.get("sex_name") or "combined").lower(),
                        int(row["year"]),
                        float(row["val"]),
                        unit,
                        GBD_ROUND,
                    ),
                )
                ingested += 1
            except (KeyError, ValueError):
                # A row missing year/val, or with a non-numeric value, is
                # skipped rather than aborting an otherwise good import.
                continue

    _set_meta(cursor, "source", csv_path)
    conn.commit()
    conn.close()

    print(f"Ingested {ingested} rows from {csv_path}.")
    return ingested


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--gbd-export",
        metavar="CSV",
        help="Path to an IHME GBD Results Tool export. Omit to load the seed data.",
    )
    args = parser.parse_args()

    if args.gbd_export:
        ingest_gbd_export(args.gbd_export)
    else:
        load_seed()

    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
