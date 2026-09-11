"""
PNG and PDF figure tests.

A downloaded figure is read far from the dashboard, so these check that the
file is real and that it carries its context: release, citation, and -- for
the prototype seed data -- a notice not to cite it. PNG text chunks and the
PDF information dictionary are stored uncompressed, so their content can be
checked directly in the bytes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import figures


def _find(client: TestClient, **dims) -> dict:
    catalogue = client.get("/api/series").json()
    matches = [s for s in catalogue if all(s[k] == v for k, v in dims.items())]
    assert len(matches) == 1, f"expected one series for {dims}, found {len(matches)}"
    return matches[0]


@pytest.fixture(scope="module")
def lung_cancer_deaths(multidim_client: TestClient) -> str:
    return _find(
        multidim_client,
        measure="Deaths",
        metric="Rate",
        age="All ages",
        sex="Both",
        cause="Lung cancer",
        risk=None,
    )["series_id"]


class TestPng:
    def test_is_a_real_png_download(self, multidim_client, lung_cancer_deaths):
        response = multidim_client.get("/api/figure.png", params={"series": lung_cancer_deaths})
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(response.content) > 20_000, "too small to be a rendered chart"
        assert response.headers["content-disposition"].endswith('.png"')

    def test_carries_release_and_ihme_citation(self, multidim_client, lung_cancer_deaths):
        body = multidim_client.get("/api/figure.png", params={"series": lung_cancer_deaths}).content
        assert b"GBD 2021" in body
        assert b"Institute for Health Metrics and Evaluation" in body


class TestPdf:
    def test_is_a_real_pdf_download(self, multidim_client, lung_cancer_deaths):
        response = multidim_client.get("/api/figure.pdf", params={"series": lung_cancer_deaths})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-")
        assert response.content.rstrip().endswith(b"%%EOF")
        assert response.headers["content-disposition"].endswith('.pdf"')

    def test_metadata_names_the_release_and_measure(self, multidim_client, lung_cancer_deaths):
        body = multidim_client.get("/api/figure.pdf", params={"series": lung_cancer_deaths}).content
        assert b"GBD 2021; Deaths; Ireland" in body


class TestContext:
    def test_requested_forecast_is_drawn_and_disclaimed(self, multidim_client, lung_cancer_deaths):
        body = multidim_client.get(
            "/api/figure.png",
            params={"series": lung_cancer_deaths, "forecast_years": 3},
        ).content
        assert b"Forecast" in body and b"not a clinical" in body

    def test_seed_data_figures_say_not_to_cite_them(self, client):
        series = client.get("/api/series").json()[0]["series_id"]
        body = client.get("/api/figure.png", params={"series": series}).content
        assert b"Do not cite" in body

    def test_real_export_figures_carry_no_prototype_notice(
        self, multidim_client, lung_cancer_deaths
    ):
        body = multidim_client.get("/api/figure.png", params={"series": lung_cancer_deaths}).content
        assert b"Do not cite" not in body

    def test_subtitle_lists_every_dimension_and_the_year_range(
        self, multidim_client, lung_cancer_deaths
    ):
        series = multidim_client.get(
            "/api/trend", params={"series": lung_cancer_deaths, "year_from": 2020}
        ).json()
        assert figures.describe(series) == (
            "Deaths · Rate (per 100,000) · All ages · Both · Ireland · 2020–2021"
        )

    def test_a_unit_that_only_repeats_the_metric_is_not_shown_twice(self, multidim_client):
        series_id = _find(multidim_client, measure="Life expectancy")["series_id"]
        series = multidim_client.get("/api/trend", params={"series": series_id}).json()
        assert figures.describe(series).startswith("Years · <1 year")

    def test_a_series_with_a_year_missing_its_interval_still_renders(self, multidim_client):
        series = _find(multidim_client, measure="Life expectancy")["series_id"]
        for fmt in ("png", "pdf"):
            assert (
                multidim_client.get(f"/api/figure.{fmt}", params={"series": series}).status_code
                == 200
            )

    def test_can_be_requested_by_dimensions_instead_of_id(self, multidim_client):
        params = {
            "measure": "Deaths",
            "metric": "Percent",
            "age": "70+ years",
            "sex": "Female",
            "cause": "Lung cancer",
            "risk": "Tobacco",
            "year_from": 2020,
            "year_to": 2021,
        }
        assert multidim_client.get("/api/figure.pdf", params=params).status_code == 200

    def test_ambiguous_or_unknown_selections_are_refused(self, multidim_client):
        assert (
            multidim_client.get("/api/figure.png", params={"measure": "Deaths"}).status_code == 409
        )
        assert multidim_client.get("/api/figure.png", params={"series": "nope"}).status_code == 404

    def test_unsupported_formats_are_rejected(self, multidim_client, lung_cancer_deaths):
        series = multidim_client.get("/api/trend", params={"series": lung_cancer_deaths}).json()
        meta = multidim_client.get("/api/meta").json()
        with pytest.raises(ValueError):
            figures.render_series(series, meta, "gif")
