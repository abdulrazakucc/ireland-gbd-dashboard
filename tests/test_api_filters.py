"""
API filter tests against the synthetic multidimensional export.

The export holds 2 measures x 3 metrics x 3 ages x 2 sexes x 3 cause/risk
pairs x 3 years, plus one life-expectancy series. Counts below follow from
that grid.
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from etl.gbd_import import import_dataset

ONE_SERIES = {
    "measure": "Deaths",
    "metric": "Rate",
    "age": "All ages",
    "sex": "Both",
    "cause": "Lung cancer",
    "risk": "",
}


class TestDimensions:
    def test_lists_every_value_of_every_dimension(self, multidim_client: TestClient) -> None:
        body = multidim_client.get("/api/dimensions").json()
        assert set(body["measure"]) == {
            "Deaths",
            "DALYs (Disability-Adjusted Life Years)",
            "Life expectancy",
        }
        assert set(body["metric"]) == {"Number", "Rate", "Percent", "Years"}
        assert set(body["age"]) == {"All ages", "Age-standardized", "70+ years", "<1 year"}
        assert set(body["sex"]) == {"Both", "Female"}
        assert set(body["cause"]) == {None, "Lung cancer", "All causes"}
        assert set(body["risk"]) == {None, "Tobacco"}
        assert (body["year_min"], body["year_max"]) == (2019, 2021)

    def test_values_narrow_to_what_the_filters_leave(self, multidim_client: TestClient) -> None:
        body = multidim_client.get("/api/dimensions", params={"measure": "Life expectancy"}).json()
        assert body["metric"] == ["Years"] and body["cause"] == [None]

    def test_an_empty_cause_selects_rows_that_have_no_cause(self, multidim_client) -> None:
        body = multidim_client.get("/api/dimensions", params={"cause": ""}).json()
        assert body["measure"] == ["Life expectancy"]


class TestSeriesFilters:
    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ({"measure": "Deaths"}, 54),
            ({"metric": "Percent"}, 36),
            ({"age": "70+ years"}, 36),
            ({"sex": "Female"}, 54),
            ({"cause": "Lung cancer"}, 72),
            ({"risk": "Tobacco"}, 72),
            ({"risk": ""}, 37),
            ({"release": "GBD 2021"}, 109),
        ],
    )
    def test_each_dimension_filters_the_catalogue(self, multidim_client, params, expected):
        catalogue = multidim_client.get("/api/series", params=params).json()
        assert len(catalogue) == expected
        ((dim, value),) = params.items()
        assert all(entry[dim] == (value or None) for entry in catalogue)

    def test_every_dimension_together_identifies_one_series(self, multidim_client) -> None:
        assert len(multidim_client.get("/api/series", params=ONE_SERIES).json()) == 1

    def test_year_range_limits_the_years_listed(self, multidim_client) -> None:
        catalogue = multidim_client.get("/api/series", params={"year_from": 2020}).json()
        assert all(entry["year_min"] >= 2020 for entry in catalogue)


class TestTrend:
    def test_points_carry_their_uncertainty_intervals(self, multidim_client) -> None:
        body = multidim_client.get("/api/trend", params=ONE_SERIES).json()
        assert body["has_uncertainty"] is True
        for point in body["series"]:
            assert point["lower"] <= point["value"] <= point["upper"]

    def test_year_range_is_inclusive(self, multidim_client) -> None:
        params = {**ONE_SERIES, "year_from": 2020, "year_to": 2020}
        body = multidim_client.get("/api/trend", params=params).json()
        assert [p["year"] for p in body["series"]] == [2020]

    def test_selection_and_series_id_return_the_same_series(self, multidim_client) -> None:
        (entry,) = multidim_client.get("/api/series", params=ONE_SERIES).json()
        by_id = multidim_client.get("/api/trend", params={"series": entry["series_id"]}).json()
        by_dims = multidim_client.get("/api/trend", params=ONE_SERIES).json()
        assert by_id == by_dims

    def test_ambiguous_selection_names_the_dimensions_still_varying(self, multidim_client) -> None:
        response = multidim_client.get("/api/trend", params={"measure": "Deaths"})
        assert response.status_code == 409
        assert set(response.json()["detail"]["varying"]) == {
            "metric",
            "age",
            "sex",
            "cause",
            "risk",
        }

    def test_reversed_year_range_is_422(self, multidim_client) -> None:
        params = {**ONE_SERIES, "year_from": 2021, "year_to": 2019}
        assert multidim_client.get("/api/trend", params=params).status_code == 422


class TestEstimates:
    def test_filters_and_pages_in_a_stable_order(self, multidim_client) -> None:
        params = {"measure": "Deaths", "metric": "Rate", "age": "All ages", "sex": "Both"}
        whole = multidim_client.get("/api/estimates", params=params).json()
        assert whole["total"] == 9
        page = multidim_client.get(
            "/api/estimates", params={**params, "limit": 4, "offset": 4}
        ).json()
        assert page["total"] == 9 and page["rows"] == whole["rows"][4:8]
        assert {"lower", "upper"} <= set(page["rows"][0])

    def test_year_filter_applies(self, multidim_client) -> None:
        body = multidim_client.get(
            "/api/estimates", params={"year_from": 2021, "limit": 10000}
        ).json()
        assert body["rows"] and {r["year"] for r in body["rows"]} == {2021}


class TestRanked:
    SELECTION = {"measure": "Deaths", "metric": "Rate", "age": "All ages", "sex": "Both"}

    def test_causes_exclude_the_total_and_risk_attributed_rows(self, multidim_client) -> None:
        body = multidim_client.get(
            "/api/ranked", params={"type": "causes", **self.SELECTION}
        ).json()
        assert [item["label"] for item in body["items"]] == ["Lung cancer"]

    def test_risks_are_ranked_on_their_all_cause_burden(self, multidim_client) -> None:
        body = multidim_client.get("/api/ranked", params={"type": "risks", **self.SELECTION}).json()
        (item,) = body["items"]
        all_cause = multidim_client.get(
            "/api/trend", params={**self.SELECTION, "cause": "All causes", "risk": "Tobacco"}
        ).json()["series"]
        assert item["label"] == "Tobacco"
        assert item["value"] == next(p["value"] for p in all_cause if p["year"] == body["year"])

    def test_latest_year_by_default_and_intervals_included(self, multidim_client) -> None:
        body = multidim_client.get(
            "/api/ranked", params={"type": "causes", **self.SELECTION}
        ).json()
        assert body["year"] == 2021
        assert body["items"][0]["lower"] is not None

    def test_an_unset_dimension_is_409(self, multidim_client) -> None:
        response = multidim_client.get(
            "/api/ranked", params={"type": "causes", "measure": "Deaths"}
        )
        assert response.status_code == 409
        assert set(response.json()["detail"]["varying"]) == {"metric", "age", "sex"}

    def test_options_list_every_rankable_combination(self, multidim_client) -> None:
        options = multidim_client.get("/api/ranked/options", params={"type": "causes"}).json()
        assert len(options) == 2 * 3 * 3 * 2 * 3


class TestCsvExport:
    def _csv(self, client: TestClient, params: dict) -> list[dict]:
        response = client.get("/api/export.csv", params=params)
        assert response.status_code == 200
        return list(csv.DictReader(io.StringIO(response.text)))

    def test_series_export_matches_the_api_including_intervals(self, multidim_client) -> None:
        trend = multidim_client.get("/api/trend", params=ONE_SERIES).json()
        rows = self._csv(multidim_client, {"series": trend["series_id"]})
        assert [
            (int(r["year"]), float(r["value"]), float(r["lower"]), float(r["upper"])) for r in rows
        ] == [(p["year"], p["value"], p["lower"], p["upper"]) for p in trend["series"]]
        assert {
            (r["release"], r["measure"], r["metric"], r["age"], r["sex"], r["cause"], r["risk"])
            for r in rows
        } == {("GBD 2021", "Deaths", "Rate", "All ages", "Both", "Lung cancer", "")}

    def test_filtered_export_holds_only_the_selection(self, multidim_client) -> None:
        rows = self._csv(
            multidim_client, {"measure": "Deaths", "age": "70+ years", "year_to": 2020}
        )
        assert len(rows) == 3 * 2 * 3 * 2
        assert all(
            r["measure"] == "Deaths" and r["age"] == "70+ years" and int(r["year"]) <= 2020
            for r in rows
        )

    def test_missing_intervals_and_dimensions_are_empty_cells(self, multidim_client) -> None:
        rows = self._csv(multidim_client, {"measure": "Life expectancy"})
        gap = next(r for r in rows if r["year"] == "2020")
        assert (gap["cause"], gap["risk"], gap["lower"], gap["upper"]) == ("", "", "", "")

    def test_an_exported_csv_can_be_imported_again(self, multidim_client, tmp_path) -> None:
        text = multidim_client.get("/api/export.csv", params={"measure": "Deaths"}).text
        path = tmp_path / "reimport_GBD_2021.csv"
        path.write_text(text, encoding="utf-8")
        report = import_dataset([path], db_path=tmp_path / "gbd.db")
        assert report.row_count == len(text.strip().splitlines()) - 1
