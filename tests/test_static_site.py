"""
Snapshot build tests.

The published site on GitHub Pages is only as trustworthy as this build. These
tests check the two things that would silently break it:

* every path the dashboard asks for exists in the output, under the exact name
  ``apiUrl()`` in ``static/index.html`` constructs;
* the snapshot carries the same values the live API returns, so publishing
  cannot quietly change a figure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a real snapshot into a temporary directory, once."""
    from scripts.build_static_site import build

    out = tmp_path_factory.mktemp("site") / "out"
    build(out)
    return out


class TestSnapshotContents:
    def test_dashboard_and_its_assets_are_copied(self, site: Path) -> None:
        assert (site / "index.html").is_file()
        assert (site / "assets" / "chart.umd.js").is_file()

    def test_config_switches_the_dashboard_into_static_mode(self, site: Path) -> None:
        """Without this the published page would call an API that is not there."""
        assert 'window.API_MODE = "static"' in (site / "config.js").read_text()

    def test_fixed_routes_are_present_and_are_valid_json(self, site: Path) -> None:
        for route in ("health", "meta", "indicators"):
            body = json.loads((site / "api" / f"{route}.json").read_text())
            assert body

    def test_meta_records_when_the_snapshot_was_built(self, site: Path) -> None:
        """Provenance: a reader must be able to see how old the figures are."""
        meta = json.loads((site / "api" / "meta.json").read_text())
        assert meta["snapshot_built"]
        assert meta["gbd_round"]

    def test_every_indicator_has_a_trend_and_a_csv(self, site: Path) -> None:
        indicators = json.loads((site / "api" / "indicators.json").read_text())
        assert indicators
        for indicator in indicators:
            ind_id = indicator["indicator_id"]
            assert (site / "api" / "trend" / f"{ind_id}.json").is_file()
            assert (site / "api" / "export" / f"{ind_id}.csv").is_file()

    def test_both_ranked_charts_are_present(self, site: Path) -> None:
        for rank_type in ("causes", "risks"):
            body = json.loads((site / "api" / "ranked" / f"{rank_type}.json").read_text())
            assert body["items"]

    def test_pages_hygiene_files_exist(self, site: Path) -> None:
        """.nojekyll stops Pages dropping files; 404.html catches stale links."""
        assert (site / ".nojekyll").is_file()
        assert (site / "404.html").is_file()


class TestSnapshotMatchesTheLiveApi:
    """The snapshot must not be able to drift from the API it was built from."""

    def test_trend_values_are_identical(self, site: Path, client: TestClient) -> None:
        indicators = json.loads((site / "api" / "indicators.json").read_text())
        for indicator in indicators:
            ind_id = indicator["indicator_id"]
            live = client.get(f"/api/trend?indicator={ind_id}").json()
            snapshot = json.loads((site / "api" / "trend" / f"{ind_id}.json").read_text())
            assert snapshot == live

    def test_ranked_values_are_identical(self, site: Path, client: TestClient) -> None:
        for rank_type in ("causes", "risks"):
            live = client.get(f"/api/ranked?type={rank_type}").json()
            snapshot = json.loads((site / "api" / "ranked" / f"{rank_type}.json").read_text())
            assert snapshot == live


class TestDashboardAgreesWithTheBuild:
    """The path mapping lives in two places; they must not disagree."""

    def test_index_loads_config_before_it_reads_api_mode(self) -> None:
        html = INDEX.read_text()
        assert 0 < html.find('src="config.js"') < html.find("const STATIC =")

    def test_index_maps_every_route_the_build_writes(self) -> None:
        html = INDEX.read_text()
        for expected in ('"api/trend/"', '"api/ranked/"', '"api/export/"'):
            assert expected in html, f"apiUrl() no longer builds {expected}"

    def test_index_uses_relative_urls_only(self) -> None:
        """A root-absolute URL would 404 under a /repo/ project-page prefix."""
        html = INDEX.read_text()
        assert not re.findall(r'(?:src|href)="/(?!/)[^"]*"', html)
