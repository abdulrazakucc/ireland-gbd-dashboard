"""
API tests against the bundled seed data.

These check the contract the dashboard depends on: the shape of each response,
the ordering guarantees, provenance, and the error codes. If one of these
fails, something the frontend relies on has changed.
"""

from __future__ import annotations

import csv
import io
import sqlite3

from fastapi.testclient import TestClient

from app import gbd
from app.main import create_app


class TestHealthAndMeta:
    def test_health_reports_ok(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_meta_reports_release_update_date_and_source_file(self, client: TestClient) -> None:
        """Every served value must be traceable to a release, a file and an import date."""
        body = client.get("/api/meta").json()
        assert body["release"] == "GBD 2023"
        assert body["imported_at"]
        assert body["row_count"] > 0 and body["series_count"] > 0
        (source,) = body["source_files"]
        assert source["filename"] == "gbd_seed.csv"
        assert len(source["sha256"]) == 64
        assert source["row_count"] == body["row_count"]
        assert "GBD 2023" in body["citation"]

    def test_seed_data_is_flagged_as_prototype(self, client: TestClient) -> None:
        body = client.get("/api/meta").json()
        assert body["prototype"] is True
        assert body["source"] == gbd.SEED_SOURCE
        assert "not a verified IHME export" in body["notice"]


class TestDatabaseProblems:
    def test_a_missing_database_is_503_with_instructions(self, tmp_path) -> None:
        client = TestClient(create_app(db_path=tmp_path / "missing.db"))
        response = client.get("/api/series")
        assert response.status_code == 503
        assert "make seed" in response.json()["detail"]

    def test_an_old_format_database_is_503_not_a_crash(self, tmp_path) -> None:
        db = tmp_path / "old.db"
        with sqlite3.connect(db) as conn:
            conn.executescript("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
        response = TestClient(create_app(db_path=db)).get("/api/meta")
        assert response.status_code == 503
        assert "make reseed" in response.json()["detail"]


class TestSeries:
    def test_catalogue_lists_every_series_with_its_years(self, client: TestClient) -> None:
        catalogue = client.get("/api/series").json()
        assert len(catalogue) == client.get("/api/meta").json()["series_count"]
        for entry in catalogue:
            assert entry["years"] == sorted(entry["years"])
            assert entry["year_min"] == entry["years"][0]
            assert {"title", "unit", "display_scale", "has_uncertainty"} <= set(entry)

    def test_trend_is_ordered_by_year_and_carries_interval_fields(self, client: TestClient) -> None:
        series = client.get("/api/series").json()[0]["series_id"]
        body = client.get("/api/trend", params={"series": series}).json()
        years = [point["year"] for point in body["series"]]
        assert years == sorted(years)
        assert set(body["series"][0]) == {"year", "value", "lower", "upper"}

    def test_percent_series_are_scaled_for_display(self, client: TestClient) -> None:
        tobacco = next(
            s
            for s in client.get("/api/series", params={"risk": "Tobacco"}).json()
            if s["measure"] == "Summary exposure value"
        )
        assert (tobacco["unit"], tobacco["display_scale"]) == ("%", 100.0)

    def test_unknown_series_is_404(self, client: TestClient) -> None:
        assert client.get("/api/trend", params={"series": "does_not_exist"}).status_code == 404

    def test_a_selection_matching_many_series_is_409_not_a_guess(self, client: TestClient) -> None:
        response = client.get("/api/trend")
        assert response.status_code == 409
        assert "measure" in response.json()["detail"]["varying"]


class TestRanked:
    def test_causes_are_ordered_high_to_low_without_the_all_causes_total(self, client) -> None:
        body = client.get("/api/ranked", params={"type": "causes"}).json()
        values = [item["value"] for item in body["items"]]
        assert values == sorted(values, reverse=True)
        assert "All causes" not in [item["label"] for item in body["items"]]
        assert body["year"] == 2023

    def test_risks_need_a_measure_when_several_could_be_ranked(self, client) -> None:
        response = client.get("/api/ranked", params={"type": "risks"})
        assert response.status_code == 409
        assert "measure" in response.json()["detail"]["varying"]

    def test_every_advertised_option_can_be_drawn(self, client) -> None:
        options = client.get("/api/ranked/options").json()
        assert options
        for option in options:
            params = {
                k: option[k]
                for k in ("type", "release", "measure", "metric", "location", "sex", "age", "year")
            }
            assert client.get("/api/ranked", params=params).status_code == 200, option

    def test_invalid_type_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/ranked", params={"type": "wombats"}).status_code == 422


class TestCsvExport:
    def test_returns_every_dimension_value_and_interval_column(self, client: TestClient) -> None:
        series = client.get("/api/series").json()[0]["series_id"]
        response = client.get("/api/export.csv", params={"series": series})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert response.headers["content-disposition"].endswith('.csv"')
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert list(rows[0]) == [
            "release",
            "measure",
            "metric",
            "location",
            "sex",
            "age",
            "cause",
            "risk",
            "year",
            "value",
            "lower",
            "upper",
        ]

    def test_unknown_series_is_404(self, client: TestClient) -> None:
        response = client.get("/api/export.csv", params={"series": "does_not_exist"})
        assert response.status_code == 404


class TestDashboard:
    def test_root_serves_the_dashboard_not_a_directory_listing(self, client: TestClient) -> None:
        """The whole point of the single-port layout: / is the dashboard."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Ireland Health Evidence" in response.text

    def test_assets_are_served(self, client: TestClient) -> None:
        for asset in ("assets/ucc-logo.png", "assets/zubair-kabir.png", "assets/chart.umd.js"):
            assert client.get(f"/{asset}").status_code == 200, asset

    def test_api_routes_win_over_the_static_catch_all(self, client: TestClient) -> None:
        """The static mount is at '/', so this ordering must not regress."""
        assert client.get("/api/health").json() == {"status": "ok"}


class TestCors:
    def test_no_cross_origin_access_by_default(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"Origin": "https://elsewhere.example"})
        assert "access-control-allow-origin" not in response.headers

    def test_only_configured_origins_are_allowed(self, seed_db) -> None:
        app = TestClient(create_app(db_path=seed_db, cors_origins=["https://ucc.ie"]))
        allowed = app.get("/api/health", headers={"Origin": "https://ucc.ie"})
        other = app.get("/api/health", headers={"Origin": "https://elsewhere.example"})
        assert allowed.headers["access-control-allow-origin"] == "https://ucc.ie"
        assert "access-control-allow-origin" not in other.headers
