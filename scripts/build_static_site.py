"""
Build the public site published to GitHub Pages.

A static site cannot check who is asking: every file on GitHub Pages can be
downloaded by anyone. So the site takes one of two shapes, decided by whether
any accounts are supplied (``GBD_USERS_JSON`` in CI, ``--users-file`` locally):

* **Landing page only** -- no accounts. The public introduction and the two
  images it shows; nothing else.

* **Landing page and sealed application** -- with accounts. The same
  application a server runs, plus every result it can show, published only as
  ciphertext:

  - every API response the application can request is collected by driving the
    real application in memory, gzip-compressed, and encrypted under a random
    256-bit key with AES-256-GCM (``app/data.sealed``);
  - that key is wrapped once per account with the account's password hash --
    PBKDF2-HMAC-SHA256 of the password, exactly what the reader's browser
    derives when they sign in (``app/keys.json``). No email address, name,
    password or password hash is published: an account is listed only by a
    SHA-256 digest of its email address.

  Every build uses a new key, so an account removed from the users file cannot
  open the next published copy.

The limits are stated plainly in the README: the protection is as strong as
each password against offline guessing, and anyone who could open a copy
keeps what they already saw.

Usage:

.. code-block:: console

    make site                                          # or, by hand:
    python -m scripts.build_static_site --out site
    python -m scripts.build_static_site --users-file data/access/users.json
    python -m scripts.build_static_site --app-url https://gbd.example.ucc.ie
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

# Allow `python scripts/build_static_site.py` as well as `python -m ...` by
# putting the repository root on the import path when run as a bare script.
if __package__ in (None, ""):  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import accounts, config  # noqa: E402

LANDING = "index.html"
IMAGES = ("ucc-logo.png", "zubair-kabir.png")
LANDING_FILES = frozenset({"index.html", "404.html", ".nojekyll", *(f"assets/{i}" for i in IMAGES)})

MAGIC = b"GBDS1"
CONTEXT = "gbd-sealed-v1"
HORIZONS = (3, 5, 10)
RANK_KEYS = ("type", "release", "measure", "metric", "location", "sex", "age", "year")
SEALED_CONFIG = """/* Written by scripts/build_static_site.py: this copy opens its results in the
   browser, from app/data.sealed, with the reader's credentials. */
window.GBD_APP = { mode: "sealed" };
"""

_BLOCK = r"[ \t]*<!-- {tag} -->.*?<!-- /{tag} -->\n?"
_MARKER = re.compile(r"[ \t]*<!-- /?ACCESS:(?:LIVE|PENDING) -->\n?")


def render_landing(page: str, app_url: str | None = None, sealed: bool = False) -> str:
    """Publish one version of the call to action, and strip the markers.

    Sealed: "Sign in" opens the application published beside the page. With an
    ``app_url``: it opens the hosted application. Otherwise: a note that access
    opens when the application launches.

    Raises:
        ValueError: if ``app_url`` is not an https URL (or local http).
    """
    base = None
    if app_url:
        parts = urlsplit(app_url.strip())
        local_http = parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost"}
        if (
            parts.scheme not in ("http", "https")
            or not parts.netloc
            or (parts.scheme != "https" and not local_http)
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise ValueError(f"--app-url must be an https URL, got {app_url!r}")
        base = html.escape(app_url.strip().rstrip("/"), quote=True)
    if sealed or base:
        page = re.sub(_BLOCK.format(tag="ACCESS:PENDING"), "", page, flags=re.S)
        if base and not sealed:
            page = page.replace('href="app/"', f'href="{base}/app/"')
    else:
        page = re.sub(_BLOCK.format(tag="ACCESS:LIVE"), "", page, flags=re.S)
    return _MARKER.sub("", page)


def request_key(route: str, params: dict | None = None) -> str:
    """The lookup key for one API request. Mirrors requestKey() in static/app/js/sealed.js."""
    entries = sorted([name, str(value)] for name, value in (params or {}).items())
    return json.dumps([route, entries], separators=(",", ":"), ensure_ascii=False)


@contextmanager
def _in_process_reader():
    # The build reads the database as a trusted local process, not over the
    # network, so sign-in -- which guards network requests -- does not apply.
    saved = config.AUTH_MODE, config.ENVIRONMENT
    config.AUTH_MODE, config.ENVIRONMENT = "off", "development"
    try:
        yield
    finally:
        config.AUTH_MODE, config.ENVIRONMENT = saved


def collect_responses(db_path: Path | None = None) -> dict[str, object]:
    """Every response the application can request, keyed by request_key()."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from etl.load_seed import ensure_database

    db_path = Path(db_path or config.DB_PATH)
    ensure_database(db_path)  # seeds only if there is nothing usable; never replaces data
    responses: dict[str, object] = {}

    with _in_process_reader(), TestClient(create_app(db_path=db_path)) as client:

        def store(route: str, params: dict | None = None) -> object:
            response = client.get(f"/api/{route}", params=params)
            if response.status_code != 200:
                raise SystemExit(
                    f"FAILED /api/{route} {params or ''} -> HTTP {response.status_code}"
                )
            responses[request_key(route, params)] = body = response.json()
            return body

        store("meta")
        catalogue = store("series")
        options = store("ranked/options")
        if not catalogue:
            raise SystemExit("Refusing to publish: the database has no series.")
        for entry in catalogue:
            store("trend", {"series": entry["series_id"]})
            for years in HORIZONS:
                store("trend", {"series": entry["series_id"], "forecast_years": years})
        for option in options:
            params = {key: option[key] for key in RANK_KEYS}
            store("ranked", params)
            for years in HORIZONS:
                store("ranked", {**params, "forecast_years": years})
    return responses


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _account_id(email: str) -> str:
    return hashlib.sha256(f"{CONTEXT}:{email.strip().lower()}".encode()).hexdigest()


def seal(bundle: dict, users: dict[str, accounts.User]) -> tuple[bytes, dict]:
    """Encrypt ``bundle`` under a fresh key, and wrap that key for each account."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plain = gzip.compress(
        json.dumps(bundle, separators=(",", ":"), ensure_ascii=False).encode(), mtime=0
    )
    key = AESGCM.generate_key(bit_length=256)
    nonce = secrets.token_bytes(12)
    sealed = MAGIC + nonce + AESGCM(key).encrypt(nonce, plain, CONTEXT.encode())

    entries = []
    for user in users.values():
        account = _account_id(user.email)
        wrap_nonce = secrets.token_bytes(12)
        entries.append(
            {
                "id": account,
                "salt": _b64(user.salt),
                "iterations": user.iterations,
                "nonce": _b64(wrap_nonce),
                "wrapped": _b64(AESGCM(user.hash).encrypt(wrap_nonce, key, account.encode())),
            }
        )
    keys = {
        "format": "gbd-sealed-keys",
        "version": 1,
        "kdf": "pbkdf2-sha256",
        "iterations": accounts.ITERATIONS,
        "users": sorted(entries, key=lambda entry: entry["id"]),
    }
    return sealed, keys


def open_sealed(sealed: bytes, keys: dict, email: str, password: str) -> dict:
    """Open a sealed copy the way a browser does. Raises on wrong credentials."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    account = _account_id(email)
    entry = next((item for item in keys["users"] if item["id"] == account), None)
    if entry is None:
        raise ValueError("No account for that email in this copy")
    wrapping = accounts.hash_password(
        password, base64.b64decode(entry["salt"]), entry["iterations"]
    )
    key = AESGCM(wrapping).decrypt(
        base64.b64decode(entry["nonce"]), base64.b64decode(entry["wrapped"]), account.encode()
    )
    if not sealed.startswith(MAGIC):
        raise ValueError("Not a sealed bundle")
    start = len(MAGIC)
    plain = AESGCM(key).decrypt(sealed[start : start + 12], sealed[start + 12 :], CONTEXT.encode())
    return json.loads(gzip.decompress(plain))


def _files(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


def build(
    out_dir: Path,
    app_url: str | None = None,
    users: dict[str, accounts.User] | None = None,
    db_path: Path | None = None,
) -> dict:
    """Write the public site to ``out_dir`` and return what was published."""
    users = users or {}
    sealed = bool(users)
    page = render_landing(
        (config.STATIC_DIR / LANDING).read_text(encoding="utf-8"), app_url, sealed
    )

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    # Unknown paths land on the landing page, not on GitHub's 404 page.
    (out_dir / "404.html").write_text(page, encoding="utf-8")
    for image in IMAGES:
        shutil.copyfile(config.STATIC_DIR / "assets" / image, out_dir / "assets" / image)
    # Without this, GitHub Pages runs the output through Jekyll.
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    expected = set(LANDING_FILES)

    responses: dict[str, object] = {}
    if sealed:
        shell = config.STATIC_DIR / "app"
        shutil.copytree(shell, out_dir / "app")
        shutil.copyfile(
            config.STATIC_DIR / "assets" / "chart.umd.js", out_dir / "assets" / "chart.umd.js"
        )
        (out_dir / "app" / "config.js").write_text(SEALED_CONFIG, encoding="utf-8")
        responses = collect_responses(db_path)
        bundle = {
            "format": "gbd-sealed-bundle",
            "version": 1,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "responses": responses,
        }
        ciphertext, keys = seal(bundle, users)
        (out_dir / "app" / "data.sealed").write_bytes(ciphertext)
        (out_dir / "app" / "keys.json").write_text(json.dumps(keys, indent=1), encoding="utf-8")
        expected |= {f"app/{name}" for name in _files(shell)} | {
            "assets/chart.umd.js",
            "app/data.sealed",
            "app/keys.json",
        }

    written = _files(out_dir)
    if written != expected:
        raise SystemExit(f"Refusing to publish unexpected files: {sorted(written ^ expected)}")
    if sealed:
        # Defence in depth: no identifier from the results may appear outside the ciphertext.
        catalogue = responses[request_key("series")]
        needles = [entry["series_id"].encode() for entry in catalogue] + [
            user.email.encode() for user in users.values()
        ]
        for name in written - {"app/data.sealed"}:
            content = (out_dir / name).read_bytes()
            if any(needle in content for needle in needles):
                raise SystemExit(
                    f"Refusing to publish: {name} contains unencrypted results or identities"
                )
    return {
        "sealed": sealed,
        "accounts": len(users),
        "responses": len(responses),
        "files": sorted(written),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the public site for GitHub Pages.")
    parser.add_argument(
        "--out", type=Path, default=config.ROOT_DIR / "site", help="Output directory"
    )
    parser.add_argument(
        "--users-file",
        type=Path,
        default=None,
        help="Seal the application for these accounts (default: the GBD_USERS_JSON variable)",
    )
    parser.add_argument(
        "--app-url",
        default=os.environ.get("GBD_APP_URL", "").strip() or None,
        help="Address of a hosted application to link to when no sealed copy is published",
    )
    args = parser.parse_args()

    users_json = os.environ.get("GBD_USERS_JSON", "").strip()
    users = (
        accounts.parse_users(users_json)
        if users_json
        else accounts.load_users(args.users_file)
        if args.users_file
        else {}
    )
    result = build(args.out, args.app_url, users)
    if result["sealed"]:
        print(
            f"Site written to {args.out}: landing page and sealed application for "
            f"{result['accounts']} account(s), {result['responses']} responses encrypted."
        )
    else:
        print(f"Site written to {args.out}: landing page only ({', '.join(result['files'])}).")


if __name__ == "__main__":
    main()
