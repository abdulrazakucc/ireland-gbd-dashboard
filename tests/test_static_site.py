"""
Public site tests.

GBD results are available only to approved users, and a static site cannot
check who is asking. So what GitHub Pages publishes must be the landing page
and nothing else: no estimates, no exports, no figures, no dashboard code.
These tests hold the build to that, and check its access links in both states.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.build_static_site import PUBLISHED, build, render_landing

ROOT = Path(__file__).resolve().parent.parent
LANDING = ROOT / "static" / "landing.html"
PENDING_TEXT = "Access requests open when the secure application launches"


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site") / "out"
    build(out)
    return out


def _published(site: Path) -> set[str]:
    return {str(p.relative_to(site)) for p in site.rglob("*") if p.is_file()}


class TestPublishesOnlyTheLandingPage:
    def test_only_the_landing_page_and_its_images_are_published(self, site: Path) -> None:
        assert _published(site) == PUBLISHED

    def test_no_results_or_dashboard_code_can_be_downloaded(self, site: Path) -> None:
        assert not (site / "api").exists()
        page = (site / "index.html").read_text()
        for forbidden in ("chart.umd.js", "config.js", "fetch(", "/api/", "api/"):
            assert forbidden not in page, f"landing page references {forbidden!r}"

    def test_the_page_introduces_the_application_and_its_access_rule(self, site: Path) -> None:
        page = (site / "index.html").read_text()
        assert "Global Health Evidence" in page
        assert "Results are available to approved users only." in page
        assert "How access works" in page

    def test_pages_hygiene_files_exist(self, site: Path) -> None:
        """.nojekyll stops Pages running Jekyll; 404.html catches stale links."""
        assert (site / ".nojekyll").is_file()
        assert (site / "404.html").read_text() == (site / "index.html").read_text()

    def test_asset_urls_are_relative(self, site: Path) -> None:
        """A root-absolute URL would 404 under the /repo/ project-page prefix."""
        page = (site / "index.html").read_text()
        assert not re.findall(r'(?:src|href)="/(?!/)[^"]*"', page)


class TestAccessLinks:
    def test_without_an_application_url_access_is_shown_as_not_yet_open(self, site) -> None:
        page = (site / "index.html").read_text()
        assert PENDING_TEXT in page
        assert 'href="register"' not in page and 'href="login"' not in page
        assert "ACCESS:" not in page

    def test_with_an_application_url_the_links_point_at_it(self, tmp_path: Path) -> None:
        build(tmp_path / "out", app_url="https://gbd.example.ucc.ie/")
        page = (tmp_path / "out" / "index.html").read_text()
        assert 'href="https://gbd.example.ucc.ie/register"' in page
        assert 'href="https://gbd.example.ucc.ie/login"' in page
        assert PENDING_TEXT not in page and "ACCESS:" not in page

    @pytest.mark.parametrize(
        "bad",
        [
            "javascript:alert(1)",
            "gbd.example.ucc.ie",
            "ftp://x",
            "http://gbd.example.ucc.ie",
            "https://user:password@gbd.example.ucc.ie",
            "https://gbd.example.ucc.ie?token=secret",
        ],
    )
    def test_an_application_url_must_be_a_web_address(self, bad: str) -> None:
        with pytest.raises(ValueError):
            render_landing(LANDING.read_text(), app_url=bad)

    def test_every_access_block_in_the_source_is_closed(self) -> None:
        source = LANDING.read_text()
        for tag in ("ACCESS:LIVE", "ACCESS:PENDING"):
            assert source.count(f"<!-- {tag} -->") == source.count(f"<!-- /{tag} -->") >= 1
