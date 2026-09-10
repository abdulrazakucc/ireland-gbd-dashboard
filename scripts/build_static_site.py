"""
Build the public site published to GitHub Pages: the landing page, and nothing else.

GBD results in this application are available only to approved users. A
static site cannot check who is asking -- every file on GitHub Pages is
public -- so no estimate, export, figure or dashboard code may ever be
published there. This build copies the landing page and the two images it
shows, and refuses to write anything else.

The landing page carries its call to action in two versions, marked in
``static/landing.html``:

* ``ACCESS:LIVE``    -- "Request access" and "Sign in" buttons;
* ``ACCESS:PENDING`` -- a note that access opens when the application launches.

With ``--app-url`` (or ``GBD_APP_URL``) the buttons are published, pointing at
the hosted application. Without one, the note is published instead.

Usage:

.. code-block:: console

    make site                                          # or, by hand:
    python -m scripts.build_static_site --out site
    python -m scripts.build_static_site --app-url https://gbd.example.ucc.ie
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Allow `python scripts/build_static_site.py` as well as `python -m ...` by
# putting the repository root on the import path when run as a bare script.
if __package__ in (None, ""):  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402

LANDING = "landing.html"
IMAGES = ("ucc-logo.png", "zubair-kabir.png")

# The complete list of what may be published. Anything else is a bug.
PUBLISHED = frozenset({"index.html", "404.html", ".nojekyll", *(f"assets/{i}" for i in IMAGES)})

_BLOCK = r"[ \t]*<!-- {tag} -->.*?<!-- /{tag} -->\n?"
_MARKER = re.compile(r"[ \t]*<!-- /?ACCESS:(?:LIVE|PENDING) -->\n?")


def render_landing(page: str, app_url: str | None = None) -> str:
    """Publish one version of the call to action, and strip the markers.

    Raises:
        ValueError: if ``app_url`` is not an http(s) URL.
    """
    if app_url:
        parts = urlsplit(app_url.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"--app-url must be an http(s) URL, got {app_url!r}")
        base = html.escape(app_url.strip().rstrip("/"), quote=True)
        page = re.sub(_BLOCK.format(tag="ACCESS:PENDING"), "", page, flags=re.S)
        page = re.sub(r'href="(register|login)"', lambda m: f'href="{base}/{m.group(1)}"', page)
    else:
        page = re.sub(_BLOCK.format(tag="ACCESS:LIVE"), "", page, flags=re.S)
    return _MARKER.sub("", page)


def build(out_dir: Path, app_url: str | None = None) -> dict:
    """Write the public site to ``out_dir`` and return what was published."""
    page = render_landing((config.STATIC_DIR / LANDING).read_text(encoding="utf-8"), app_url)

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

    written = {str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()}
    if written != PUBLISHED:
        raise SystemExit(f"Refusing to publish unexpected files: {sorted(written ^ PUBLISHED)}")
    return {"app_url": app_url or None, "files": sorted(written)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the public GitHub Pages landing page.")
    parser.add_argument(
        "--out",
        type=Path,
        default=config.ROOT_DIR / "site",
        help="Directory to write the site to (default: <repo>/site)",
    )
    parser.add_argument(
        "--app-url",
        default=os.environ.get("GBD_APP_URL", "").strip() or None,
        help="Address of the hosted application (default: GBD_APP_URL). "
        "Without it, the page says access opens when the application launches.",
    )
    args = parser.parse_args()

    result = build(args.out, args.app_url)
    print(f"Landing page written to {args.out}: {', '.join(result['files'])}")
    print(f"  access links: {result['app_url'] or 'not yet open (no application URL)'}")


if __name__ == "__main__":
    main()
