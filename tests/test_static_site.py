"""
Public site tests.

A static site cannot check who is asking. So what GitHub Pages publishes is
either the landing page alone, or the landing page with a sealed application
whose results only valid credentials can decrypt. These tests hold the build to
both shapes, and prove the sealed copy opens -- and only opens -- the way a
reader's browser opens it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from fastapi.testclient import TestClient

from app import accounts
from scripts.build_static_site import (
    HORIZONS,
    LANDING_FILES,
    RANK_KEYS,
    build,
    open_sealed,
    render_landing,
    request_key,
)

ROOT = Path(__file__).resolve().parent.parent
LANDING = ROOT / "static" / "index.html"
PENDING_TEXT = "Access requests open when the secure application launches"
EMAIL = "presenter@example.org"
PASSWORD = "a long presentation password"


@pytest.fixture(scope="module")
def landing_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("landing") / "site"
    build(out)
    return out


@pytest.fixture(scope="module")
def users(tmp_path_factory: pytest.TempPathFactory) -> dict[str, accounts.User]:
    path = tmp_path_factory.mktemp("access") / "users.json"
    accounts.add_user(EMAIL, PASSWORD, "Presenter", path)
    accounts.add_user("colleague@example.org", "another long password", "", path)
    return accounts.load_users(path)


@pytest.fixture(scope="module")
def sealed_site(tmp_path_factory: pytest.TempPathFactory, users, seed_db: Path) -> Path:
    out = tmp_path_factory.mktemp("sealed") / "site"
    build(out, users=users, db_path=seed_db)
    return out


def _published(site: Path) -> set[str]:
    return {str(p.relative_to(site)) for p in site.rglob("*") if p.is_file()}


def _open(site: Path, email: str = EMAIL, password: str = PASSWORD) -> dict:
    keys = json.loads((site / "app" / "keys.json").read_text())
    return open_sealed((site / "app" / "data.sealed").read_bytes(), keys, email, password)


class TestLandingOnly:
    def test_only_the_landing_page_and_its_images_are_published(self, landing_site) -> None:
        assert _published(landing_site) == LANDING_FILES

    def test_no_application_results_or_dashboard_code(self, landing_site) -> None:
        assert not (landing_site / "app").exists() and not (landing_site / "api").exists()
        page = (landing_site / "index.html").read_text()
        for forbidden in ("chart.umd.js", "fetch(", "/api/"):
            assert forbidden not in page, forbidden

    def test_the_page_introduces_the_application_and_its_access_rule(self, landing_site) -> None:
        page = (landing_site / "index.html").read_text()
        assert "Global Health Evidence" in page
        assert "Results are available to approved users only." in page
        assert "How access works" in page

    def test_pages_hygiene_files_exist(self, landing_site) -> None:
        assert (landing_site / ".nojekyll").is_file()
        assert (landing_site / "404.html").read_text() == (landing_site / "index.html").read_text()

    def test_asset_urls_are_relative(self, landing_site) -> None:
        """A root-absolute URL would 404 under the /repo/ project-page prefix."""
        assert not re.findall(
            r'(?:src|href)="/(?!/)[^"]*"', (landing_site / "index.html").read_text()
        )


class TestAccessLinks:
    def test_without_accounts_or_an_application_access_is_not_yet_open(self, landing_site) -> None:
        page = (landing_site / "index.html").read_text()
        assert PENDING_TEXT in page
        assert 'href="app/"' not in page and "ACCESS:" not in page

    def test_a_hosted_application_is_linked_by_its_address(self) -> None:
        page = render_landing(LANDING.read_text(), app_url="https://gbd.example.ucc.ie/")
        assert 'href="https://gbd.example.ucc.ie/app/"' in page
        assert PENDING_TEXT not in page and "ACCESS:" not in page

    def test_a_sealed_copy_is_linked_beside_the_page(self, sealed_site) -> None:
        page = (sealed_site / "index.html").read_text()
        assert 'href="app/"' in page and PENDING_TEXT not in page

    @pytest.mark.parametrize(
        "bad", ["javascript:alert(1)", "gbd.example.ucc.ie", "http://example.org"]
    )
    def test_an_application_url_must_be_https(self, bad: str) -> None:
        with pytest.raises(ValueError):
            render_landing(LANDING.read_text(), app_url=bad)

    def test_every_access_block_in_the_source_is_closed(self) -> None:
        source = LANDING.read_text()
        for tag in ("ACCESS:LIVE", "ACCESS:PENDING"):
            assert source.count(f"<!-- {tag} -->") == source.count(f"<!-- /{tag} -->") >= 1


class TestSealedApplication:
    def test_publishes_the_landing_page_the_application_and_ciphertext_only(
        self, sealed_site
    ) -> None:
        files = _published(sealed_site)
        assert LANDING_FILES <= files
        assert {
            "app/index.html",
            "app/js/main.js",
            "app/data.sealed",
            "app/keys.json",
            "assets/chart.umd.js",
        } <= files
        assert not any(name.startswith("api/") for name in files)

    def test_the_published_application_reads_the_sealed_copy(self, sealed_site) -> None:
        assert 'mode: "sealed"' in (sealed_site / "app" / "config.js").read_text()

    def test_no_email_name_or_password_hash_is_published(self, sealed_site, users) -> None:
        everything = b"".join((sealed_site / name).read_bytes() for name in _published(sealed_site))
        for user in users.values():
            assert user.email.encode() not in everything
            assert accounts._b64(user.hash).encode() not in everything
        assert b"Presenter" not in everything
        entry_fields = {
            frozenset(entry)
            for entry in json.loads((sealed_site / "app" / "keys.json").read_text())["users"]
        }
        assert entry_fields == {frozenset({"id", "salt", "iterations", "nonce", "wrapped"})}

    def test_no_result_appears_outside_the_ciphertext(self, sealed_site) -> None:
        catalogue = _open(sealed_site)["responses"][request_key("series")]
        for name in _published(sealed_site) - {"app/data.sealed"}:
            content = (sealed_site / name).read_bytes()
            assert not any(entry["series_id"].encode() in content for entry in catalogue), name

    def test_every_account_opens_the_same_results(self, sealed_site) -> None:
        first = _open(sealed_site)
        second = _open(sealed_site, "colleague@example.org", "another long password")
        assert first == second and first["responses"]

    def test_the_sealed_results_match_the_live_api(self, sealed_site, client: TestClient) -> None:
        responses = _open(sealed_site)["responses"]
        assert responses[request_key("meta")] == client.get("/api/meta").json()
        catalogue = responses[request_key("series")]
        assert catalogue == client.get("/api/series").json()
        for entry in catalogue[:5]:
            params = {"series": entry["series_id"], "forecast_years": 5}
            assert (
                responses[request_key("trend", params)]
                == client.get("/api/trend", params=params).json()
            )
        option = responses[request_key("ranked/options")][0]
        params = {key: option[key] for key in RANK_KEYS}
        assert (
            responses[request_key("ranked", params)]
            == client.get("/api/ranked", params=params).json()
        )

    def test_every_view_the_application_offers_is_included(self, sealed_site) -> None:
        responses = _open(sealed_site)["responses"]
        for entry in responses[request_key("series")]:
            for extra in ({}, *({"forecast_years": years} for years in HORIZONS)):
                assert request_key("trend", {"series": entry["series_id"], **extra}) in responses
        for option in responses[request_key("ranked/options")]:
            params = {key: option[key] for key in RANK_KEYS}
            for extra in ({}, *({"forecast_years": years} for years in HORIZONS)):
                assert request_key("ranked", {**params, **extra}) in responses

    def test_a_wrong_password_opens_nothing(self, sealed_site) -> None:
        with pytest.raises(InvalidTag):
            _open(sealed_site, password="not the right password")

    def test_an_unknown_email_opens_nothing(self, sealed_site) -> None:
        with pytest.raises(ValueError):
            _open(sealed_site, email="stranger@example.org")

    def test_an_account_removed_before_a_rebuild_is_locked_out(
        self, tmp_path, users, seed_db
    ) -> None:
        remaining = {EMAIL: users[EMAIL]}
        out = tmp_path / "site"
        build(out, users=remaining, db_path=seed_db)
        assert _open(out)["responses"]
        with pytest.raises(ValueError):
            _open(out, "colleague@example.org", "another long password")


class TestApplicationShell:
    def test_the_shell_has_no_inline_scripts(self) -> None:
        """Every script is a file, so the Content-Security-Policy needs no inline exception."""
        shell = (ROOT / "static" / "app" / "index.html").read_text()
        assert not re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", shell)
        assert shell.index('src="config.js"') < shell.index('src="js/main.js"')

    def test_request_keys_match_the_browser_format(self) -> None:
        assert request_key("trend", {"series": "abc", "forecast_years": 5}) == (
            '["trend",[["forecast_years","5"],["series","abc"]]]'
        )
        sealed_js = (ROOT / "static" / "app" / "js" / "sealed.js").read_text()
        assert "JSON.stringify([route, entries])" in sealed_js
