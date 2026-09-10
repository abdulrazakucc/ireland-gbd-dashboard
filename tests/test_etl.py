"""
Seed data tests.

The bundled seed goes through the same importer as a real GBD export. These
check that it still loads, that loading it again is repeatable, and that the
entry points other tooling calls -- including the bare-script form used by
scripts/install.ps1 -- keep working.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app import config, gbd
from etl.gbd_import import COLUMN_ALIASES, _resolve_columns
from etl.load_seed import load_seed

ROOT = Path(__file__).resolve().parent.parent


def _snapshot(db: Path) -> list[tuple]:
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT * FROM gbd_estimate ORDER BY series_id, year").fetchall()


def test_seed_file_is_in_gbd_results_tool_format() -> None:
    header = config.SEED_CSV.read_text(encoding="utf-8").splitlines()[0].split(",")
    columns, problems = _resolve_columns(header, config.SEED_CSV.name)
    assert problems == []
    assert set(columns) == set(COLUMN_ALIASES)


def test_seed_loads_every_row_and_is_marked_as_prototype(seed_db) -> None:
    with sqlite3.connect(seed_db) as conn:
        meta = dict(conn.execute("SELECT key, value FROM meta"))
    data_rows = len(config.SEED_CSV.read_text(encoding="utf-8").splitlines()) - 1
    assert meta["row_count"] == str(data_rows)
    assert meta["source"] == gbd.SEED_SOURCE
    assert meta["release"] == config.GBD_ROUND


def test_seeding_twice_gives_identical_data(tmp_path) -> None:
    db = tmp_path / "gbd.db"
    load_seed(db)
    first = _snapshot(db)
    load_seed(db)
    assert _snapshot(db) == first


def test_bare_script_invocation_still_works(tmp_path) -> None:
    """scripts/install.ps1 and INSTALL_WINDOWS.md run `python etl/load_seed.py`."""
    env = {**os.environ, "GBD_DB_PATH": str(tmp_path / "gbd.db")}
    result = subprocess.run(
        [sys.executable, "etl/load_seed.py", "--ensure"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "gbd.db").is_file()
