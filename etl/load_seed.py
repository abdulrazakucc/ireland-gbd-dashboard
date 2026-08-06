"""
ETL for the UCC School of Public Health Ireland GBD Dashboard.

Two ingestion paths are provided:

1. load_seed()          - loads the bundled seed CSVs (data gathered during
                           prototype development). Use this to get the
                           pipeline running immediately.

2. ingest_gbd_export()  - a REAL adapter for the actual public IHME
                           GBD Results Tool bulk CSV export format
                           (https://vizhub.healthdata.org/gbd-results/).
                           Point this at a real downloaded export and it
                           will populate the same database schema, ready
                           for the API to serve. This is the path to a
                           genuinely live pipeline: IHME does not offer a
                           free-form real-time query API, so "live" in
                           practice means "re-run this script whenever a
                           new GBD round or extract is downloaded."

Usage:
    python etl/load_seed.py                 # seed with prototype data
    python etl/load_seed.py --gbd-export path/to/IHME-GBD_2023_DATA.csv
"""
import argparse
import csv
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app" / "gbd.db"
SEED_TREND = Path(__file__).resolve().parent.parent / "data" / "gbd_seed.csv"
SEED_RANKED = Path(__file__).resolve().parent.parent / "data" / "gbd_ranked_seed.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trend_indicator (
    indicator_id TEXT NOT NULL,
    indicator_label TEXT NOT NULL,
    location TEXT NOT NULL,
    sex TEXT NOT NULL,
    year INTEGER NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    gbd_round TEXT NOT NULL,
    PRIMARY KEY (indicator_id, location, sex, year)
);

CREATE TABLE IF NOT EXISTS ranked_indicator (
    rank_type TEXT NOT NULL,
    label TEXT NOT NULL,
    location TEXT NOT NULL,
    year INTEGER NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    gbd_round TEXT NOT NULL,
    PRIMARY KEY (rank_type, label, location, year)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def load_seed():
    conn = get_conn()
    cur = conn.cursor()

    with open(SEED_TREND, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [
            (r["indicator_id"], r["indicator_label"], r["location"], r["sex"],
             int(r["year"]), float(r["value"]), r["unit"], r["gbd_round"])
            for r in reader
        ]
    cur.executemany(
        "INSERT OR REPLACE INTO trend_indicator "
        "(indicator_id, indicator_label, location, sex, year, value, unit, gbd_round) "
        "VALUES (?,?,?,?,?,?,?,?)", rows,
    )
    print(f"Loaded {len(rows)} trend rows.")

    with open(SEED_RANKED, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [
            (r["rank_type"], r["label"], r["location"], int(r["year"]),
             float(r["value"]), r["unit"], r["gbd_round"])
            for r in reader
        ]
    cur.executemany(
        "INSERT OR REPLACE INTO ranked_indicator "
        "(rank_type, label, location, year, value, unit, gbd_round) "
        "VALUES (?,?,?,?,?,?,?)", rows,
    )
    print(f"Loaded {len(rows)} ranked rows.")

    cur.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('gbd_round', 'GBD 2023')"
    )
    cur.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('source', 'seed_prototype_data')"
    )
    conn.commit()
    conn.close()


def ingest_gbd_export(csv_path: str, indicator_map: dict | None = None):
    """
    Ingest a real IHME GBD Results Tool bulk CSV export.

    The public export schema (as of GBD 2023) has columns similar to:
      measure_name, location_name, sex_name, age_name, cause_name / rei_name,
      metric_name, year, val, upper, lower

    `indicator_map` lets you map (cause_name or rei_name) -> your own
    short indicator_id, e.g. {"Tobacco": "tobacco_sev"}. If not supplied,
    the raw name is slugified and used as-is, so this will run against any
    export without configuration, but mapped IDs are recommended so the
    frontend's indicator dropdown stays stable across re-ingests.
    """
    import re

    def slugify(s):
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

    conn = get_conn()
    cur = conn.cursor()
    n = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = r.get("cause_name") or r.get("rei_name") or r.get("indicator_name")
            if not name:
                continue
            indicator_id = (indicator_map or {}).get(name, slugify(name))
            metric = (r.get("metric_name") or "").lower()
            unit = "percent" if metric == "percent" else (r.get("metric_name") or "value")
            try:
                cur.execute(
                    "INSERT OR REPLACE INTO trend_indicator "
                    "(indicator_id, indicator_label, location, sex, year, value, unit, gbd_round) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        indicator_id, name, r.get("location_name", "Ireland"),
                        (r.get("sex_name") or "combined").lower(),
                        int(r["year"]), float(r["val"]), unit, "GBD 2023",
                    ),
                )
                n += 1
            except (KeyError, ValueError):
                continue
    cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('source', ?)", (csv_path,))
    conn.commit()
    conn.close()
    print(f"Ingested {n} rows from {csv_path}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gbd-export", help="Path to a real IHME GBD Results Tool CSV export")
    args = parser.parse_args()

    if args.gbd_export:
        ingest_gbd_export(args.gbd_export)
    else:
        load_seed()
