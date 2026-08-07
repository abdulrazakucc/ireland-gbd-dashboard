"""
API tests.

These check the contract the dashboard depends on: the shape of each response,
the ordering guarantees, and the error codes. If one of these fails, something
the frontend relies on has changed.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthAndMeta:
    def test_health_reports_ok(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_meta_records_provenance(self, client: TestClient) -> None:
        """Every served value must be traceable to a GBD round and a source."""
        body = client.get("/api/meta").json()
        assert body["gbd_round"]
        assert body["source"]


class TestIndicators:
    def test_lists_indicators_with_the_fields_the_dropdown_needs(self, client: TestClient) -> None:
        body = client.get("/api/indicators").json()
        assert body, "seed data should provide at least one indicator"
        assert set(body[0]) == {"indicator_id", "indicator_label", "unit"}

    def test_sorted_by_label(self, client: TestClient) -> None:
        labels = [item["indicator_label"] for item in client.get("/api/indicators").json()]
        assert labels == sorted(labels)


class TestTrend:
    def test_returns_a_series_ordered_by_year(self, client: TestClient, any_indicator: str) -> None:
        body = client.get("/api/trend", params={"indicator": any_indicator}).json()
        years = [point["year"] for point in body["series"]]
        assert years == sorted(years)
        assert body["indicator"] == any_indicator
        assert body["unit"]

    def test_unknown_indicator_is_404(self, client: TestClient) -> None:
        response = client.get("/api/trend", params={"indicator": "does_not_exist"})
        assert response.status_code == 404

    def test_unknown_location_is_404_not_an_empty_series(self, client: TestClient) -> None:
        """An empty chart would look like real data; a 404 cannot be mistaken."""
        response = client.get("/api/trend", params={"indicator": "le", "location": "Atlantis"})
        assert response.status_code == 404

    def test_indicator_is_required(self, client: TestClient) -> None:
        assert client.get("/api/trend").status_code == 422


class TestRanked:
    def test_causes_are_ordered_high_to_low(self, client: TestClient) -> None:
        items = client.get("/api/ranked", params={"type": "causes"}).json()["items"]
        values = [item["value"] for item in items]
        assert values == sorted(values, reverse=True)

    def test_risks_are_available_too(self, client: TestClient) -> None:
        body = client.get("/api/ranked", params={"type": "risks"}).json()
        assert body["type"] == "risks"
        assert body["items"]

    def test_invalid_type_is_rejected(self, client: TestClient) -> None:
        response = client.get("/api/ranked", params={"type": "wombats"})
        assert response.status_code == 422


class TestCsvExport:
    def test_returns_csv_with_a_header_and_a_filename(
        self, client: TestClient, any_indicator: str
    ) -> None:
        response = client.get("/api/export.csv", params={"indicator": any_indicator})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert any_indicator in response.headers["content-disposition"]

        lines = response.text.strip().splitlines()
        assert lines[0].startswith("indicator_id,")
        assert len(lines) > 1, "expected at least one data row"

    def test_unknown_indicator_is_404(self, client: TestClient) -> None:
        response = client.get("/api/export.csv", params={"indicator": "does_not_exist"})
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
