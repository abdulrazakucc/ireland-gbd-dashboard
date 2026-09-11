"""
API tests against the bundled seed data.

These check the contract the dashboard depends on: the shape of each response,
the ordering guarantees, provenance, and the error codes. If one of these
fails, something the frontend relies on has changed.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3

import pytest
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
        assert source["label"] == "Approved source 1"
        assert "filename" not in source and "sha256" not in source and "bytes" not in source
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

    def test_forecast_is_optional_bounded_and_transparent(self, multidim_client) -> None:
        series = multidim_client.get("/api/series").json()[0]["series_id"]
        observed = multidim_client.get("/api/trend", params={"series": series}).json()
        assert observed["forecast"] == [] and observed["forecast_info"] is None

        body = multidim_client.get(
            "/api/trend", params={"series": series, "forecast_years": 5}
        ).json()
        assert [point["year"] for point in body["forecast"]] == list(range(2022, 2027))
        assert body["forecast_info"]["status"] == "available"
        assert body["forecast_info"]["training_points"] == 3
        assert "not a clinical" in body["forecast_info"]["note"]
        assert all(point["lower"] <= point["value"] <= point["upper"] for point in body["forecast"])

    def test_forecast_horizon_is_limited(self, multidim_client) -> None:
        assert multidim_client.get("/api/trend", params={"forecast_years": 11}).status_code == 422


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

    def test_ranking_can_include_projected_values(self, multidim_client) -> None:
        options = multidim_client.get("/api/ranked/options", params={"type": "causes"}).json()
        option = max(options, key=lambda item: item["year"])
        params = {
            key: option[key]
            for key in ("type", "release", "measure", "metric", "location", "sex", "age", "year")
        }
        params["forecast_years"] = 3
        body = multidim_client.get("/api/ranked", params=params).json()
        assert body["forecast_year"] == option["year"] + 3
        assert len(body["forecast_items"]) == len(body["items"])
        assert body["forecast_info"]["status"] == "available"


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

    def test_forecast_export_labels_observed_and_projected_rows(self, multidim_client) -> None:
        series = multidim_client.get("/api/series").json()[0]["series_id"]
        response = multidim_client.get(
            "/api/export.csv", params={"series": series, "forecast_years": 3}
        )
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert {row["record_type"] for row in rows} == {"observed", "forecast"}
        assert all(row["forecast_method"] == "" for row in rows if row["record_type"] == "observed")
        assert all(
            row["forecast_method"] == "Linear trend (ordinary least squares)"
            for row in rows
            if row["record_type"] == "forecast"
        )


class TestDashboard:
    def test_root_serves_the_dashboard_not_a_directory_listing(self, client: TestClient) -> None:
        """The whole point of the single-port layout: / is the dashboard."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Global Health Evidence" in response.text

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


class TestSecurity:
    def test_production_refuses_to_start_without_authentication(self, monkeypatch) -> None:
        from app import config

        monkeypatch.setattr(config, "ENVIRONMENT", "production")
        monkeypatch.setattr(config, "AUTH_MODE", "off")
        monkeypatch.setattr(config, "PROXY_SECRET", "")
        with pytest.raises(RuntimeError, match="Production starts only"):
            create_app()

    def test_sensitive_responses_are_not_cached_and_have_browser_guards(self, client) -> None:
        response = client.get("/api/meta")
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    def test_proxy_mode_fails_closed_except_for_health(self, seed_db, monkeypatch) -> None:
        from app import config

        monkeypatch.setattr(config, "AUTH_MODE", "proxy")
        monkeypatch.setattr(config, "PROXY_SECRET", "unit-test-secret-that-is-long-enough")
        app = TestClient(create_app(db_path=seed_db))
        assert app.get("/api/health").status_code == 200
        assert app.get("/api/meta").status_code == 401
        authenticated = app.get(
            "/api/meta",
            headers={
                "X-Forwarded-User": "approved-researcher",
                "X-GBD-Proxy-Secret": "unit-test-secret-that-is-long-enough",
            },
        )
        assert authenticated.status_code == 200

    def test_database_errors_do_not_expose_server_paths(self, tmp_path) -> None:
        missing = tmp_path / "private" / "research.db"
        body = TestClient(create_app(db_path=missing)).get("/api/meta").json()
        assert str(missing) not in body["detail"]


class TestNoApiInformationExposed:
    """The dashboard is for results, not for advertising the API behind it."""

    def test_api_documentation_is_not_served_by_default(self, client: TestClient) -> None:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404, path

    def test_api_documentation_is_off_in_development_too(self, seed_db, monkeypatch) -> None:
        import importlib

        import app.config

        monkeypatch.setenv("GBD_ENV", "development")
        monkeypatch.delenv("GBD_EXPOSE_DOCS", raising=False)
        assert importlib.reload(app.config).EXPOSE_DOCS is False
        importlib.reload(app.config)

    def test_api_documentation_can_be_switched_on_for_development(self, seed_db, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "EXPOSE_DOCS", True)
        app = TestClient(create_app(db_path=seed_db))
        for path in ("/docs", "/openapi.json"):
            assert app.get(path).status_code == 200, path

    def test_dashboard_shows_no_api_reference_or_api_addresses(self, client: TestClient) -> None:
        page = client.get("/").text
        for text in ("API reference", "Live API", "Served live from", "/docs", "thin client"):
            assert text not in page, text

    def test_dashboard_does_not_name_its_server_technology(self, client: TestClient) -> None:
        """Developer comments in the source may; the page a reader sees may not."""
        page = client.get("/").text
        markup = re.sub(
            r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", "", page, flags=re.S
        )
        assert "FastAPI" not in markup
