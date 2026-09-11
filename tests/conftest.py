"""
Shared test fixtures.

Nothing here touches ``data/gbd.db``. ``GBD_DB_PATH`` is pointed at a throwaway
directory before anything from ``app`` or ``etl`` is imported, as a backstop,
and every fixture passes an explicit database path besides.

Two datasets are available:

* the bundled **seed** data, exactly as ``make seed`` builds it;
* a synthetic **multidimensional** export in the IHME Results Tool "ID and
  name" layout, with several measures, metrics, ages, sexes, causes, risks and
  uncertainty intervals at once. Every value is distinct, so a row that
  overwrote another would be visible. The numbers are made up.
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

os.environ["GBD_DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="gbd-tests-")) / "unused.db")
os.environ.pop("GBD_CORS_ORIGINS", None)
os.environ.pop("GBD_EXPOSE_DOCS", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPORT_HEADER = [
    "measure_name", "location_name", "sex_name", "age_name", "cause_name",
    "rei_name", "metric_name", "year", "val", "upper", "lower",
]  # fmt: skip

MEASURES = ("Deaths", "DALYs (Disability-Adjusted Life Years)")
METRICS = ("Number", "Rate", "Percent")
AGES = ("All ages", "Age-standardized", "70+ years")
SEXES = ("Both", "Female")
CAUSE_RISK = (("Lung cancer", ""), ("All causes", "Tobacco"), ("Lung cancer", "Tobacco"))
YEARS = (2019, 2020, 2021)


def _multidim_rows() -> list[dict[str, str]]:
    rows, n = [], 0
    for measure in MEASURES:
        for metric in METRICS:
            for age in AGES:
                for sex in SEXES:
                    for cause, rei in CAUSE_RISK:
                        for year in YEARS:
                            n += 1
                            value = n / 1000 if metric == "Percent" else n * 10.0
                            rows.append({
                                "measure_name": measure, "location_name": "Ireland",
                                "sex_name": sex, "age_name": age, "cause_name": cause,
                                "rei_name": rei, "metric_name": metric, "year": str(year),
                                "val": repr(value), "lower": repr(round(value * 0.9, 6)),
                                "upper": repr(round(value * 1.1, 6)),
                            })  # fmt: skip
    # A series with neither cause nor risk, and one year with no interval.
    for year, value, lower, upper in (
        (2019, 82.1, 81.8, 82.4),
        (2020, 81.9, "", ""),
        (2021, 82.3, 82.0, 82.6),
    ):
        rows.append({
            "measure_name": "Life expectancy", "location_name": "Ireland", "sex_name": "Both",
            "age_name": "<1 year", "cause_name": "", "rei_name": "", "metric_name": "Years",
            "year": str(year), "val": str(value), "lower": str(lower), "upper": str(upper),
        })  # fmt: skip
    return rows


def _write_export(path: Path, rows: list[dict[str, str]], header: list[str] | None = None) -> Path:
    header = header or EXPORT_HEADER
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture()
def multidim_rows() -> list[dict[str, str]]:
    """A fresh, mutable copy of the synthetic export's rows."""
    return _multidim_rows()


@pytest.fixture()
def export_header() -> list[str]:
    """The IHME "ID and name" header the synthetic export uses."""
    return list(EXPORT_HEADER)


@pytest.fixture()
def write_export() -> Callable[..., Path]:
    """``write_export(path, rows, header=None)`` writes rows as an IHME-style CSV."""
    return _write_export


@pytest.fixture(scope="session")
def seed_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from etl.load_seed import load_seed

    path = tmp_path_factory.mktemp("seed") / "gbd.db"
    load_seed(path)
    return path


@pytest.fixture(scope="session")
def client(seed_db: Path) -> Iterator[TestClient]:
    """A TestClient serving the seed data."""
    from app.main import create_app

    with TestClient(create_app(db_path=seed_db)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def multidim_export(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # Named like a real download, so the release is taken from the filename.
    folder = tmp_path_factory.mktemp("export")
    return _write_export(folder / "IHME-GBD_2021_DATA-test-1.csv", _multidim_rows())


@pytest.fixture(scope="session")
def multidim_db(tmp_path_factory: pytest.TempPathFactory, multidim_export: Path) -> Path:
    from etl.gbd_import import import_dataset

    path = tmp_path_factory.mktemp("multidim") / "gbd.db"
    import_dataset([multidim_export], db_path=path)
    return path


@pytest.fixture(scope="session")
def multidim_client(multidim_db: Path) -> Iterator[TestClient]:
    """A TestClient serving the synthetic multidimensional export."""
    from app.main import create_app

    with TestClient(create_app(db_path=multidim_db)) as test_client:
        yield test_client
