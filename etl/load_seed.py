"""
ETL command line: build the SQLite database the API reads.

Every load -- the bundled seed data included -- goes through
:func:`etl.gbd_import.import_dataset`: validate the files, build a *new*
database beside the live one, verify it, and only then swap it in atomically.
A failed load changes nothing.

Why there is no "fetch from IHME" function: IHME publishes GBD in annual
rounds as bulk downloads. There is no free real-time query API to call, so
re-running this when a new round lands *is* the update mechanism.

Usage:

.. code-block:: console

    make seed                                    # seed only if there is no usable database
    python -m etl.load_seed                      # rebuild from the bundled seed data
    python -m etl.load_seed --ensure             # what `make seed` and Docker run
    python -m etl.load_seed --gbd-export data/incoming/IHME-GBD_2023_DATA-1.csv
    python -m etl.load_seed --gbd-export part-1.csv part-2.csv --release "GBD 2023"
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

# Allow `python etl/load_seed.py` as well as `python -m etl.load_seed` by
# putting the repository root on the import path when run as a bare script.
if __package__ in (None, ""):  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, gbd  # noqa: E402  (import must follow the path bootstrap)
from app.db import SCHEMA_VERSION  # noqa: E402
from etl.gbd_import import GBDImportError, ImportReport, import_dataset  # noqa: E402

# How the seed was labelled before schema version 2.
_LEGACY_SEED_SOURCE = "seed_prototype_data"


class OutdatedDatabaseError(RuntimeError):
    """An old-format database holds imported data that cannot be rebuilt automatically."""


def load_seed(db_path: Path | None = None) -> ImportReport:
    """Rebuild the database from the bundled prototype data."""
    return import_dataset(
        [config.SEED_CSV], release=config.GBD_ROUND, source=gbd.SEED_SOURCE, db_path=db_path
    )


def ingest_gbd_export(
    paths: str | Path | Sequence[str | Path],
    release: str | None = None,
    db_path: Path | None = None,
) -> ImportReport:
    """Rebuild the database from one GBD Results Tool export (one or more files)."""
    files = [paths] if isinstance(paths, str | Path) else list(paths)
    return import_dataset(files, release=release, db_path=db_path)


def ensure_database(db_path: Path | None = None) -> str:
    """Make sure a usable database exists, without ever discarding imported data.

    Returns ``"current"``, ``"seeded"`` (there was none) or ``"reseeded"`` (an
    old-format copy of the seed data was rebuilt).

    Raises:
        OutdatedDatabaseError: an old-format database holds something other
            than seed data. Rebuilding it from the seed would silently swap a
            real import for prototype numbers, so that is left to a person.
    """
    path = Path(db_path or config.DB_PATH)
    if not path.exists():
        load_seed(path)
        return "seeded"
    try:
        with sqlite3.connect(path) as conn:
            meta = dict(conn.execute("SELECT key, value FROM meta"))
    except sqlite3.DatabaseError:
        meta = {}
    if meta.get("schema_version") == str(SCHEMA_VERSION):
        return "current"
    if meta.get("source") in (gbd.SEED_SOURCE, _LEGACY_SEED_SOURCE):
        load_seed(path)
        return "reseeded"
    raise OutdatedDatabaseError(
        f"{path} was built by an older version of this project from "
        f"{meta.get('source') or 'an unknown source'}. Re-import that GBD export with "
        "`make refresh`, or replace it with the seed data using `make reseed`."
    )


def _print_report(report: ImportReport) -> None:
    print(
        f"Imported {report.release} ({report.source}): {report.row_count} estimates "
        f"in {report.series_count} series."
    )
    for f in report.files:
        print(f"  {f.filename}  {f.row_count} rows  sha256 {f.sha256[:16]}...")
    print(f"Active database: {report.db_path}")
    if report.previous:
        print(f"Previous database kept at: {report.previous}")
    for warning in report.warnings:
        print(f"Warning: {warning}")


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description="Build the GBD database the API reads.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--gbd-export",
        nargs="+",
        metavar="CSV",
        help="One IHME GBD Results Tool export (several files if the download was split).",
    )
    group.add_argument(
        "--ensure",
        action="store_true",
        help="Seed only if there is no database, or an old-format copy of the seed.",
    )
    parser.add_argument(
        "--release", help="GBD release label, e.g. 'GBD 2023'. Default: from the filename."
    )
    args = parser.parse_args(argv)

    try:
        if args.ensure:
            outcome = ensure_database()
            print(f"Database {outcome}: {config.DB_PATH}")
        elif args.gbd_export:
            _print_report(ingest_gbd_export(args.gbd_export, release=args.release))
        else:
            _print_report(load_seed())
    except (GBDImportError, OutdatedDatabaseError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
