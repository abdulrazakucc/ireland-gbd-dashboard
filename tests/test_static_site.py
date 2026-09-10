"""
Snapshot build tests.

The published site on GitHub Pages is only as trustworthy as this build. These
tests check the two things that would silently break it:

* every file the dashboard can ask for exists in the output, under the exact
  name ``apiUrl()`` in ``static/index.html`` constructs;
* the snapshot carries the same values the live API returns, so publishing
  cannot quietly change a figure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.build_static_site import RANK_KEYS

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, seed_db: Path) -> Path:
    """Build a real snapshot of the seed database into a temporary directory, once."""
    from scripts.build_static_site import build

    out = tmp_path_factory.mktemp("site") / "out"
    build(out, db_path=seed_db)
    return out


def _json(site: Path, relative: str):
    return json.loads((site / "api" / relative).read_text())


class TestSnapshotContents:
    def test_dashboard_and_its_assets_are_copied(self, site: Path) -> None:
        assert (site / "index.html").is_file()
        assert (site / "assets" / "chart.umd.js").is_file()

    def test_config_switches_the_dashboard_into_static_mode(self, site: Path) -> None:
        """Without this the published page would call an API that is not there."""
        assert 'window.API_MODE = "static"' in (site / "config.js").read_text()

    def test_fixed_routes_are_present_and_are_valid_json(self, site: Path) -> None:
        for route in ("health", "meta", "series", "dimensions", "ranked/options"):
            assert _json(site, f"{route}.json")

    def test_meta_records_release_source_and_when_the_snapshot_was_built(self, site) -> None:
        """Provenance: a reader must be able to see how old the figures are."""
        meta = _json(site, "meta.json")
        assert meta["snapshot_built"] and meta["release"] and meta["imported_at"]
        assert meta["source_files"][0]["sha256"]

    def test_every_series_has_its_trend_csv_png_and_pdf(self, site: Path) -> None:
        catalogue = _json(site, "series.json")
        assert catalogue
        for entry in catalogue:
            sid = entry["series_id"]
            assert _json(site, f"trend/{sid}.json")["series"]
            assert (site / "api" / "export" / f"{sid}.csv").read_text().startswith("release,")
            assert (site / "api" / "figure" / f"{sid}.png").read_bytes().startswith(b"\x89PNG")
            assert (site / "api" / "figure" / f"{sid}.pdf").read_bytes().startswith(b"%PDF-")

    def test_every_ranking_option_names_a_file_that_exists(self, site: Path) -> None:
        options = _json(site, "ranked/options.json")
        assert options
        for option in options:
            assert _json(site, option["file"])["items"]

    def test_pages_hygiene_files_exist(self, site: Path) -> None:
        """.nojekyll stops Pages dropping files; 404.html catches stale links."""
        assert (site / ".nojekyll").is_file()
        assert (site / "404.html").is_file()


class TestSnapshotMatchesTheLiveApi:
    """The snapshot must not be able to drift from the API it was built from."""

    def test_series_values_and_intervals_are_identical(self, site, client: TestClient) -> None:
        for entry in _json(site, "series.json"):
            sid = entry["series_id"]
            assert (
                _json(site, f"trend/{sid}.json")
                == client.get("/api/trend", params={"series": sid}).json()
            )
            assert (site / "api" / "export" / f"{sid}.csv").read_text() == client.get(
                "/api/export.csv", params={"series": sid}
            ).text

    def test_rankings_are_identical(self, site, client: TestClient) -> None:
        for option in _json(site, "ranked/options.json"):
            params = {k: option[k] for k in RANK_KEYS}
            assert _json(site, option["file"]) == client.get("/api/ranked", params=params).json()


class TestDashboardAgreesWithTheBuild:
    """The path mapping lives in two places; they must not disagree."""

    def test_index_loads_config_before_it_reads_api_mode(self) -> None:
        html = INDEX.read_text()
        assert 0 < html.find('src="config.js"') < html.find("const STATIC =")

    def test_index_maps_every_route_the_build_writes(self) -> None:
        html = INDEX.read_text()
        for expected in ('"api/trend/"', '"api/export/"', '"api/figure/"', '"api/" + hit.file'):
            assert expected in html, f"apiUrl() no longer builds {expected}"

    def test_index_looks_rankings_up_by_the_same_keys_the_build_uses(self) -> None:
        match = re.search(r"const RANK_KEYS = \[([^\]]*)\]", INDEX.read_text())
        assert match, "RANK_KEYS not found in index.html"
        assert re.findall(r'"([a-z_]+)"', match.group(1)) == list(RANK_KEYS)

    def test_published_snapshot_hides_the_api_reference(self) -> None:
        """A static site has no API behind it, so listing endpoints there would be dead links."""
        html = INDEX.read_text()
        assert 'id="apiSection"' in html
        assert '$("apiSection").hidden = STATIC;' in html

    def test_index_uses_relative_urls_only(self) -> None:
        """A root-absolute URL would 404 under a /repo/ project-page prefix."""
        html = INDEX.read_text()
        assert not re.findall(r'(?:src|href)="/(?!/)[^"]*"', html)
