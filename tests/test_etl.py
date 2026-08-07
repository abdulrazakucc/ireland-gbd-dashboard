"""
ETL tests.

The load must be **idempotent**: `make refresh` runs on a schedule, so a
second run of the same data has to leave the database identical rather than
doubling every row.
"""

from __future__ import annotations

import csv
import sqlite3

import pytest


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    """Seed a throwaway database and hand back a path to it."""
    db_path = tmp_path / "etl.db"
    monkeypatch.setenv("GBD_DB_PATH", str(db_path))

    # Reimport under the patched environment so config picks up the new path.
    import importlib

    import app.config
    import etl.load_seed

    importlib.reload(app.config)
    importlib.reload(etl.load_seed)

    etl.load_seed.load_seed()
    return db_path, etl.load_seed


def _count(db_path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_seed_populates_all_three_tables(seeded_db) -> None:
    db_path, _ = seeded_db
    assert _count(db_path, "trend_indicator") > 0
    assert _count(db_path, "ranked_indicator") > 0
    assert _count(db_path, "meta") > 0


def test_seeding_twice_does_not_duplicate_rows(seeded_db) -> None:
    db_path, module = seeded_db
    before = _count(db_path, "trend_indicator")
    module.load_seed()
    assert _count(db_path, "trend_indicator") == before


def test_gbd_export_adapter_maps_real_column_names(seeded_db, tmp_path) -> None:
    """A minimal export in the IHME Results Tool shape should ingest cleanly."""
    db_path, module = seeded_db
    export = tmp_path / "IHME-GBD_TEST_DATA.csv"

    with open(export, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["rei_name", "location_name", "sex_name", "year", "val", "metric_name"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "rei_name": "Second-hand smoke",
                "location_name": "Ireland",
                "sex_name": "Both",
                "year": "2023",
                "val": "3.5",
                "metric_name": "Percent",
            }
        )

    assert module.ingest_gbd_export(str(export)) == 1

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT indicator_id, indicator_label, sex, unit FROM trend_indicator "
            "WHERE indicator_id = 'second_hand_smoke'"
        ).fetchone()

    assert row == ("second_hand_smoke", "Second-hand smoke", "both", "percent")


def test_indicator_map_keeps_ids_stable(seeded_db, tmp_path) -> None:
    """Mapped IDs are what protect the dashboard from IHME rewording a label."""
    _, module = seeded_db
    export = tmp_path / "export.csv"

    with open(export, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rei_name", "year", "val", "metric_name"])
        writer.writeheader()
        writer.writerow(
            {"rei_name": "Tobacco", "year": "2023", "val": "7.7", "metric_name": "Percent"}
        )

    module.ingest_gbd_export(str(export), indicator_map={"Tobacco": "tobacco_sev"})

    import app.config

    with sqlite3.connect(app.config.DB_PATH) as conn:
        ids = [r[0] for r in conn.execute("SELECT indicator_id FROM trend_indicator")]

    assert "tobacco_sev" in ids
    assert "tobacco" not in ids


def test_malformed_rows_are_skipped_not_fatal(seeded_db, tmp_path) -> None:
    """One bad row must not abort an otherwise good import."""
    _, module = seeded_db
    export = tmp_path / "messy.csv"

    with open(export, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rei_name", "year", "val", "metric_name"])
        writer.writeheader()
        writer.writerow({"rei_name": "Good", "year": "2023", "val": "1.0", "metric_name": "Rate"})
        writer.writerow({"rei_name": "Bad", "year": "n/a", "val": "x", "metric_name": "Rate"})

    assert module.ingest_gbd_export(str(export)) == 1
