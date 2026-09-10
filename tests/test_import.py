"""
Importer tests.

Two promises are tested here. First, every GBD dimension survives an import,
so estimates that differ by measure, metric, age, sex, cause or risk can never
overwrite one another, and uncertainty intervals arrive intact. Second, an
import that fails for any reason leaves the active database byte-for-byte
unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from etl import gbd_import
from etl.gbd_import import (
    EXPORT_SOURCE,
    DuplicateRecordsError,
    GBDImportError,
    ValidationError,
    VerificationError,
    import_dataset,
)


def _rows(db: Path, where: str = "", params: tuple = ()) -> list[dict]:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(f"SELECT * FROM gbd_estimate {where}", params)]


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestDimensionsAreKeptApart:
    def test_every_input_row_becomes_exactly_one_estimate(self, multidim_db, multidim_export):
        with open(multidim_export, newline="") as handle:
            expected = sum(1 for _ in csv.DictReader(handle))
        assert len(_rows(multidim_db)) == expected

    def test_multiple_measures_coexist(self, multidim_db):
        rows = _rows(
            multidim_db,
            "WHERE metric='Rate' AND age='All ages' AND sex='Both' "
            "AND cause='Lung cancer' AND risk='' AND year=2020",
        )
        assert {r["measure"] for r in rows} == {"Deaths", "DALYs (Disability-Adjusted Life Years)"}
        assert len({r["value"] for r in rows}) == 2

    def test_multiple_metrics_coexist(self, multidim_db):
        rows = _rows(
            multidim_db,
            "WHERE measure='Deaths' AND age='All ages' AND sex='Both' "
            "AND cause='Lung cancer' AND risk='' AND year=2020",
        )
        assert {r["metric"] for r in rows} == {"Number", "Rate", "Percent"}
        assert len({r["value"] for r in rows}) == 3

    def test_multiple_ages_coexist(self, multidim_db):
        rows = _rows(
            multidim_db,
            "WHERE measure='Deaths' AND metric='Rate' AND sex='Both' "
            "AND cause='Lung cancer' AND risk='' AND year=2020",
        )
        assert {r["age"] for r in rows} == {"All ages", "Age-standardized", "70+ years"}
        assert len({r["value"] for r in rows}) == 3

    def test_cause_and_risk_are_independent_dimensions(self, multidim_db):
        rows = _rows(
            multidim_db,
            "WHERE measure='Deaths' AND metric='Rate' AND sex='Both' "
            "AND age='All ages' AND year=2020 AND measure <> 'Life expectancy'",
        )
        assert {(r["cause"], r["risk"]) for r in rows} == {
            ("Lung cancer", ""),
            ("All causes", "Tobacco"),
            ("Lung cancer", "Tobacco"),
        }

    def test_release_is_stored_on_every_row(self, multidim_db):
        assert {r["release"] for r in _rows(multidim_db)} == {"GBD 2021"}

    def test_name_only_download_style_is_accepted(self, tmp_path, write_export, multidim_rows):
        renamed = [{k.removesuffix("_name"): v for k, v in r.items()} for r in multidim_rows]
        header = [
            "measure",
            "location",
            "sex",
            "age",
            "cause",
            "rei",
            "metric",
            "year",
            "val",
            "upper",
            "lower",
        ]
        path = write_export(tmp_path / "names-only.csv", renamed, header)
        report = import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")
        assert report.row_count == len(multidim_rows)


class TestUncertaintyIntervals:
    def test_lower_and_upper_are_preserved_exactly(self, multidim_db, multidim_rows):
        source = next(
            r
            for r in multidim_rows
            if r["measure_name"] == "Deaths"
            and r["metric_name"] == "Rate"
            and r["age_name"] == "All ages"
            and r["sex_name"] == "Both"
            and r["cause_name"] == "Lung cancer"
            and r["rei_name"] == ""
            and r["year"] == "2020"
        )
        stored = _rows(
            multidim_db,
            "WHERE measure='Deaths' AND metric='Rate' AND age='All ages' "
            "AND sex='Both' AND cause='Lung cancer' AND risk='' AND year=2020",
        )[0]
        assert (stored["value"], stored["lower"], stored["upper"]) == (
            float(source["val"]),
            float(source["lower"]),
            float(source["upper"]),
        )

    def test_a_year_without_an_interval_is_null_not_zero(self, multidim_db):
        row = _rows(multidim_db, "WHERE measure='Life expectancy' AND year=2020")[0]
        assert row["lower"] is None and row["upper"] is None

    @pytest.mark.parametrize(
        ("change", "message"),
        [
            ({"upper": ""}, "uncertainty interval needs numeric lower and upper"),
            ({"lower": "50", "upper": "40"}, "exceeds upper"),
            (
                {"metric_name": "Percent", "val": "12.5", "lower": "11", "upper": "14"},
                "proportions",
            ),
        ],
    )
    def test_invalid_intervals_are_refused(
        self, tmp_path, write_export, multidim_rows, change, message
    ):
        multidim_rows[0].update(change)
        path = write_export(tmp_path / "bad.csv", multidim_rows)
        with pytest.raises(ValidationError, match=message):
            import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")


class TestDuplicateDetection:
    def test_identical_duplicate_rows_are_refused(self, tmp_path, write_export, multidim_rows):
        path = write_export(tmp_path / "dup.csv", [*multidim_rows, multidim_rows[5]])
        with pytest.raises(DuplicateRecordsError, match="identical values"):
            import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")

    def test_conflicting_duplicate_rows_are_refused(self, tmp_path, write_export, multidim_rows):
        clash = {**multidim_rows[5], "val": "999", "lower": "900", "upper": "1000"}
        path = write_export(tmp_path / "dup.csv", [*multidim_rows, clash])
        with pytest.raises(DuplicateRecordsError, match="conflicting values") as caught:
            import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")
        assert "line 7" in str(caught.value) and "line " + str(len(multidim_rows) + 2) in str(
            caught.value
        ), "both offending lines should be named"

    def test_a_duplicate_split_across_files_names_both_files(
        self, tmp_path, write_export, multidim_rows
    ):
        first = write_export(tmp_path / "part-1.csv", multidim_rows[:10])
        second = write_export(tmp_path / "part-2.csv", multidim_rows[9:20])
        with pytest.raises(DuplicateRecordsError) as caught:
            import_dataset([first, second], release="GBD 2021", db_path=tmp_path / "gbd.db")
        assert "part-1.csv" in str(caught.value) and "part-2.csv" in str(caught.value)

    def test_split_files_without_overlap_import_as_one_dataset(
        self, tmp_path, write_export, multidim_rows
    ):
        first = write_export(tmp_path / "part-1.csv", multidim_rows[:10])
        second = write_export(tmp_path / "part-2.csv", multidim_rows[10:])
        report = import_dataset([first, second], release="GBD 2021", db_path=tmp_path / "gbd.db")
        assert report.row_count == len(multidim_rows)
        assert [f.filename for f in report.files] == ["part-1.csv", "part-2.csv"]


class TestValidation:
    def test_missing_required_column_is_refused(
        self, tmp_path, write_export, multidim_rows, export_header
    ):
        header = [h for h in export_header if h != "metric_name"]
        path = write_export(tmp_path / "no-metric.csv", multidim_rows, header)
        with pytest.raises(ValidationError, match="missing required column"):
            import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")

    def test_ambiguous_columns_are_refused(
        self, tmp_path, write_export, multidim_rows, export_header
    ):
        for row in multidim_rows:
            row["measure"] = row["measure_name"]
        path = write_export(tmp_path / "both.csv", multidim_rows, [*export_header, "measure"])
        with pytest.raises(ValidationError, match="ambiguous columns for measure"):
            import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")

    def test_one_invalid_row_fails_the_whole_import_with_its_line(
        self, tmp_path, write_export, multidim_rows
    ):
        multidim_rows[1]["year"] = "n/a"
        path = write_export(tmp_path / "messy.csv", multidim_rows)
        with pytest.raises(ValidationError, match="messy.csv line 3: year 'n/a'"):
            import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")

    def test_an_empty_file_is_refused(self, tmp_path, write_export):
        path = write_export(tmp_path / "empty.csv", [])
        with pytest.raises(ValidationError, match="no data rows"):
            import_dataset([path], release="GBD 2021", db_path=tmp_path / "gbd.db")


class TestFailedImportLeavesTheActiveDatabaseUntouched:
    @pytest.fixture()
    def live_db(self, tmp_path) -> Path:
        from etl.load_seed import load_seed

        path = tmp_path / "live" / "gbd.db"
        path.parent.mkdir()
        load_seed(path)
        return path

    def _assert_untouched(self, db: Path, before: str) -> None:
        assert _fingerprint(db) == before
        leftovers = [p.name for p in db.parent.iterdir() if p.name != db.name]
        assert leftovers == [], f"a failed import left files behind: {leftovers}"

    @pytest.mark.parametrize("problem", ["missing column", "invalid value", "duplicate", "no file"])
    def test_refused_import(
        self, live_db, tmp_path, write_export, multidim_rows, export_header, problem
    ):
        before = _fingerprint(live_db)
        path = tmp_path / "incoming.csv"
        if problem == "missing column":
            write_export(path, multidim_rows, [h for h in export_header if h != "val"])
        elif problem == "invalid value":
            multidim_rows[-1]["val"] = "not-a-number"
            write_export(path, multidim_rows)
        elif problem == "duplicate":
            write_export(path, [*multidim_rows, multidim_rows[0]])
        with pytest.raises(GBDImportError):
            import_dataset([path], release="GBD 2021", db_path=live_db)
        self._assert_untouched(live_db, before)

    def test_failed_verification_is_never_activated(self, live_db, multidim_export, monkeypatch):
        before = _fingerprint(live_db)

        def fail(*args, **kwargs):
            raise VerificationError("simulated verification failure")

        monkeypatch.setattr(gbd_import, "verify_database", fail)
        with pytest.raises(VerificationError):
            import_dataset([multidim_export], db_path=live_db)
        self._assert_untouched(live_db, before)

    def test_success_swaps_in_the_new_database_and_keeps_the_previous(
        self, live_db, multidim_export
    ):
        before = _fingerprint(live_db)
        report = import_dataset([multidim_export], db_path=live_db)
        assert report.previous == live_db.with_name("gbd.db.previous")
        assert _fingerprint(report.previous) == before
        assert {r["release"] for r in _rows(live_db)} == {"GBD 2021"}

    def test_a_running_app_serves_the_new_data_without_a_restart(self, live_db, multidim_export):
        from app.main import create_app

        with TestClient(create_app(db_path=live_db)) as client:
            assert client.get("/api/meta").json()["release"] == "GBD 2023"
            import_dataset([multidim_export], db_path=live_db)
            assert client.get("/api/meta").json()["release"] == "GBD 2021"

    def test_command_line_reports_failure_and_changes_nothing(
        self, live_db, tmp_path, write_export, multidim_rows, monkeypatch, capsys
    ):
        import app.config
        from etl import load_seed

        before = _fingerprint(live_db)
        monkeypatch.setattr(app.config, "DB_PATH", live_db)
        path = write_export(tmp_path / "dup.csv", [*multidim_rows, multidim_rows[0]])
        assert load_seed.main(["--gbd-export", str(path), "--release", "GBD 2021"]) == 1
        assert "left unchanged" in capsys.readouterr().err
        self._assert_untouched(live_db, before)


class TestProvenance:
    def test_release_date_source_row_count_and_checksum_are_recorded(
        self, multidim_db, multidim_export
    ):
        with sqlite3.connect(multidim_db) as conn:
            meta = dict(conn.execute("SELECT key, value FROM meta"))
            files = conn.execute(
                "SELECT filename, sha256, bytes, row_count FROM source_file"
            ).fetchall()
        assert meta["release"] == "GBD 2021"  # taken from the filename
        assert meta["source"] == EXPORT_SOURCE
        assert datetime.fromisoformat(meta["imported_at"]).tzinfo is not None
        rows = len(_rows(multidim_db))
        assert meta["row_count"] == str(rows)
        assert files == [
            (
                multidim_export.name,
                _fingerprint(multidim_export),
                multidim_export.stat().st_size,
                rows,
            )
        ]

    def test_only_the_file_name_is_stored_never_the_server_path(self, multidim_db):
        with sqlite3.connect(multidim_db) as conn:
            (filename,) = conn.execute("SELECT filename FROM source_file").fetchone()
        assert "/" not in filename and "\\" not in filename

    def test_a_release_contradicting_the_filename_is_refused(self, multidim_export, tmp_path):
        with pytest.raises(ValidationError, match="contradicts the filename"):
            import_dataset([multidim_export], release="GBD 2023", db_path=tmp_path / "gbd.db")

    def test_release_falls_back_to_the_configured_round(
        self, tmp_path, write_export, multidim_rows
    ):
        import app.config

        path = write_export(tmp_path / "export.csv", multidim_rows)
        report = import_dataset([path], db_path=tmp_path / "gbd.db")
        assert report.release == app.config.GBD_ROUND


class TestEnsureDatabase:
    def _old_format(self, path: Path, source: str) -> None:
        with sqlite3.connect(path) as conn:
            conn.executescript(
                "CREATE TABLE trend_indicator (indicator_id TEXT);"
                "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
            )
            conn.execute("INSERT INTO meta VALUES ('source', ?)", (source,))

    def test_a_missing_database_is_seeded(self, tmp_path):
        from etl.load_seed import ensure_database

        assert ensure_database(tmp_path / "gbd.db") == "seeded"

    def test_a_current_database_is_left_alone(self, tmp_path, multidim_export):
        from etl.load_seed import ensure_database

        db = tmp_path / "gbd.db"
        import_dataset([multidim_export], db_path=db)
        before = _fingerprint(db)
        assert ensure_database(db) == "current"
        assert _fingerprint(db) == before

    def test_an_old_format_copy_of_the_seed_is_rebuilt(self, tmp_path):
        from etl.load_seed import ensure_database

        db = tmp_path / "gbd.db"
        self._old_format(db, "seed_prototype_data")
        assert ensure_database(db) == "reseeded"
        assert len(_rows(db)) > 0

    def test_an_old_format_real_import_is_never_replaced_by_seed_data(self, tmp_path):
        from etl.load_seed import OutdatedDatabaseError, ensure_database

        db = tmp_path / "gbd.db"
        self._old_format(db, "data/incoming/IHME-GBD_2021_DATA.csv")
        before = _fingerprint(db)
        with pytest.raises(OutdatedDatabaseError, match="make refresh"):
            ensure_database(db)
        assert _fingerprint(db) == before
