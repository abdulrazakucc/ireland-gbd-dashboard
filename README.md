<div align="center">

# Ireland Health Evidence

**A working ETL → API → dashboard pipeline for Global Burden of Disease indicators for Ireland**

School of Public Health · University College Cork · Cork, Ireland

`Python 3.11+` · `FastAPI` · `SQLite` · `Docker` · `no build step`

</div>

---

**Principal Investigator** — [Dr. Zubair Kabir](https://research.ucc.ie/en/persons/zubair-kabir/),
Senior Lecturer, School of Public Health, University College Cork.

---

## Table of contents

- [What this is](#what-this-is)
- [Before you start](#before-you-start)
- [Quick start](#quick-start)
- [All commands](#all-commands)
- [Everyday recipes](#everyday-recipes)
- [Repository structure](#repository-structure)
- [What each directory is for](#what-each-directory-is-for)
- [How it works](#how-it-works)
- [The API](#the-api)
- [The dashboard](#the-dashboard)
- [Loading real GBD data](#loading-real-gbd-data)
- [Testing and code quality](#testing-and-code-quality)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Data governance and attribution](#data-governance-and-attribution)

---

## What this is

Three pieces that fit together:

```
   IHME GBD export                  SQLite                     Browser
   (annual bulk CSV)                database
        │                              │                          │
        │   etl/load_seed.py           │   app/ (FastAPI)         │
        └─────────────────────────────►│◄─────────────────────────┘
              ingest, once per round        live HTTP on every page load
```

The **dashboard-to-API** link is genuinely live: the page holds no data of its
own, and every number on screen comes from an HTTP request answered from the
database. The **API-to-IHME** link is a scheduled ingest, because that is how
GBD is actually published (see
[What "live" honestly means](#what-live-honestly-means)).

New to the project? You only need **one** command: `make dev`.

## Before you start

You need three things, and you probably already have all of them:

| | Why | Check it |
|---|---|---|
| **Python 3.11 or newer** | Runs the application | `python3 --version` |
| **`make`** | Runs every command in this project | `make --version` |
| **`curl`** | Used by `make smoke` | `curl --version` |

Docker is **optional** — only needed if you prefer `make up` over running
locally.

<details>
<summary><b>Don't have them? (click to expand)</b></summary>

- **macOS** — Python: [python.org/downloads](https://www.python.org/downloads/)
  or `brew install python`. `make` and `curl` come with Xcode Command Line
  Tools: `xcode-select --install`.
- **Windows** — install [Python](https://www.python.org/downloads/) ticking
  *"Add python.exe to PATH"*, then use **WSL** (Ubuntu) or **Git Bash** so that
  `make` is available. In WSL: `sudo apt install make curl`.
  *No admin rights, or not comfortable with WSL?* Use
  [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) instead — it installs Python with
  pyenv into your own user folder and skips `make` entirely.
- **Linux** — `sudo apt install python3 python3-venv make curl`.

</details>

**One command checks all of it for you**, and tells you exactly what is missing
and how to fix it:

```bash
make doctor
```

```
==> Checking your setup
    Python 3.11+          ok (found 3.12)
    make                  ok
    curl                  ok
    Docker (optional)     ok and running
    Virtual environment   not created yet -- run: make setup
    Database              not built yet -- run: make seed
    Port 8000             free
```

### Getting into the project folder

Every command below must be run **from inside the project folder**. Open a
terminal and change into it first:

```bash
cd path/to/ucc_gbd_pipeline
```

You are in the right place if `ls` shows a `Makefile`.

## Quick start

> **On Windows, or new to the command line?** Follow
> **[INSTALL_WINDOWS.md](INSTALL_WINDOWS.md)** instead — a step-by-step guide
> written for non-technical users, which needs no admin rights on either
> Windows or Mac.

### The one-command version

```bash
make dev
```

That does everything: creates the virtual environment, installs dependencies,
builds the database, starts the app, and opens the dashboard in your browser.
It takes about a minute the first time and a few seconds afterwards.

When you are finished:

```bash
make stop
```

### Or step by step

If you would rather see each stage, the same thing in three commands:

```bash
make setup     # 1. create .venv and install pinned dependencies
make seed      # 2. build the database from the seed CSVs
make run       # 3. start the app
```

### Or in Docker

Nothing to install but Docker itself — no Python, no virtual environment:

```bash
make up        # build and start
make down      # stop
```

Either way, **one process serves everything on one port**:

| | |
|---|---|
| **Dashboard** | <http://127.0.0.1:8000> |
| **JSON API** | <http://127.0.0.1:8000/api/...> |
| **Interactive API docs** | <http://127.0.0.1:8000/docs> |

There is no separate frontend server and no HTML file to open by hand. Confirm
everything is working with `make smoke`.

To stop: `make down` (Docker) or `make stop` (local).

## All commands

Every command lives in the [`Makefile`](Makefile). **Run `make` on its own** to
print this list in your terminal at any time — you never have to remember it.

You always type `make` followed by the name, e.g. `make run`. Order does not
matter: each command sets up whatever it needs first. `make run` will build the
database if it is missing; `make test` will install the test tools if they are
not there.

### Shortcuts — the four worth remembering

| Command | What it does |
|---|---|
| **`make dev`** | **Everything at once**: install, build the database, start, open the browser. Use this the first time. |
| `make start` | Start the app (a friendlier name for `make run`) |
| `make doctor` | Check this machine has what the project needs |
| `make urls` | Print the addresses the app serves on |

`make install` also works, as another name for `make setup`.

### Running the app locally

| Command | What it does |
|---|---|
| `make setup` | Create `.venv` and install runtime dependencies |
| `make setup-dev` | Also install test and lint tools |
| `make seed` | Build the database from the seed CSVs (skipped if up to date) |
| `make reseed` | Delete and rebuild the database from scratch |
| `make run` | Start the app in the background |
| `make stop` | Stop it |
| `make restart` | Stop, then start |
| `make status` | Show what is listening on the port |
| `make open` | Open the dashboard in a browser |
| `make logs` | Follow the app log |

### Running the app in Docker

| Command | What it does |
|---|---|
| `make up` | Build the image and start the container |
| `make down` | Stop and remove it (frees the port) |
| `make docker-restart` | Rebuild and restart |
| `make docker-logs` | Follow the container log |
| `make docker-ps` | Show container status and health |

### Quality checks

| Command | What it does |
|---|---|
| `make test` | Run the test suite |
| `make lint` | Check code style and formatting |
| `make format` | Auto-fix formatting and import order |
| `make smoke` | Check a **running** app answers on every endpoint |
| `make check` | `lint` + `test` — exactly what CI runs |

### Data and housekeeping

| Command | What it does |
|---|---|
| `make refresh` | Ingest the newest GBD export from `data/incoming/` |
| `make clean` | Remove the database, logs, and caches (keeps `.venv`) |
| `make distclean` | Also remove `.venv` |

## Everyday recipes

Find what you want to do, then run the command beside it.

| I want to… | Command |
|---|---|
| Run it for the very first time | `make dev` |
| Start it again tomorrow | `make start` |
| Stop it | `make stop` |
| See it in my browser | `make open` |
| Find out which address it is on | `make urls` |
| Check whether it is actually working | `make smoke` |
| See what the app is doing right now | `make logs` *(press `Ctrl+C` to stop watching)* |
| Find out why it will not start | `make doctor`, then `make status` |
| Pick up my changes to `index.html` | Just refresh the browser — no restart needed |
| Pick up my changes to Python code | `make restart` |
| Load a new GBD export | Put the CSV in `data/incoming/`, then `make refresh` |
| Rebuild the database from scratch | `make reseed` |
| Check my changes did not break anything | `make check` |
| Tidy up formatting before committing | `make format` |
| Start completely fresh | `make distclean` then `make dev` |

### A first session, start to finish

```bash
cd path/to/ucc_gbd_pipeline

make doctor        # confirm this machine is ready
make dev           # install, build, start, open browser
make smoke         # confirm every endpoint answers

# ... use the dashboard at http://127.0.0.1:8000 ...

make stop          # finished for now
```

> **A note on `make run` and `make up`.** They do the same thing by different
> routes, and both use **port 8000** — so only one can run at a time. If you
> started with `make up` (Docker), stop it with `make down` before using
> `make run`, and vice versa. `make status` always tells you which is running.

## Repository structure

```
ucc_gbd_pipeline/
│
├── app/                          The web application (API + serves the dashboard)
│   ├── __init__.py
│   ├── config.py                 Every path and setting, resolved once
│   ├── db.py                     SQLite access helpers
│   ├── schemas.py                Response models -> these generate /docs
│   ├── routes.py                 The /api routes
│   └── main.py                   App factory; mounts the dashboard at /
│
├── etl/                          Getting data INTO the database
│   ├── __init__.py
│   └── load_seed.py              Seed loader + real GBD Results Tool adapter
│
├── data/                         All data lives here (never in the code dirs)
│   ├── gbd_seed.csv              Prototype seed data: trend indicators
│   ├── gbd_ranked_seed.csv       Prototype seed data: top causes and risks
│   ├── gbd.db                    SQLite database — BUILT, not committed
│   └── incoming/                 Drop new GBD Results Tool exports here
│
├── static/                       The frontend, served at /
│   ├── index.html                The whole dashboard: one file, no build step
│   └── assets/
│       ├── ucc-logo.png          Cropped, web-sized UCC logo
│       ├── zubair-kabir.png      Principal investigator photograph
│       └── chart.umd.js          Chart.js, vendored — no CDN dependency
│
├── tests/                        Test suite (pytest)
│   ├── conftest.py               Shared fixtures; builds a temporary database
│   ├── test_api.py               Every endpoint's contract
│   └── test_etl.py               Ingest correctness and idempotency
│
├── scripts/
│   └── refresh.sh                Scheduled re-ingestion (cron-friendly)
│
├── docker/
│   └── entrypoint.sh             Seeds the database on first container start
│
├── brand/                        Original high-resolution identity assets
│   ├── ucc-logo.png              Source logo (the web copy is in static/assets)
│   └── zubair-kabir.png          Source photograph
│
├── .github/workflows/
│   └── ci.yml                    Lint, test, and a real container build
│
├── Makefile                      Every command for this project
├── Dockerfile                    Container image definition
├── docker-compose.yml            One service, one port
├── requirements.txt              Runtime dependencies, pinned
├── requirements-dev.txt          Test and lint dependencies, pinned
├── pyproject.toml                ruff and pytest configuration
├── .gitignore                    Build artefacts and licensed data stay out
├── .dockerignore                 Keeps the image small and clean
└── README.md                     This file
```

## What each directory is for

### `app/` — the web application

The API and the dashboard are served by **one** FastAPI application on **one**
port. The package is split by responsibility so each file has one job:

| File | Responsibility |
|---|---|
| `config.py` | The single source of truth for **where things are**. Nothing else in the codebase works out a path by walking `__file__`. Every path can be overridden with an environment variable, which is how Docker and the tests point the app elsewhere without editing code. |
| `db.py` | Opening SQLite connections and running queries. If this project ever moves to Postgres, **this is the only file that changes**. |
| `schemas.py` | Pydantic models describing every response. They document the API at `/docs`, give the frontend a contract, and make a shape change fail loudly in tests. |
| `routes.py` | The `/api` endpoints. Thin: each one is a query plus a little shaping. |
| `main.py` | Builds the application — middleware, routes, and the static mount. |

**One ordering rule matters here.** The dashboard is mounted at `/`, which is a
catch-all. FastAPI matches routes in declaration order, so the `/api` router is
registered **before** the static mount. Reverse them and every API call would
return the HTML page instead. `tests/test_api.py` guards this.

### `etl/` — getting data in

`load_seed.py` has two entry points:

- **`load_seed()`** loads the bundled CSVs in `data/`. This is what runs
  automatically the first time you start the app, so there is always something
  to look at.
- **`ingest_gbd_export()`** is the adapter for a real IHME bulk export. It maps
  the Results Tool's column names onto the same tables, so **neither the API
  nor the dashboard changes** when you switch from seed data to real data.

Both are idempotent: the tables use composite primary keys, so re-running the
ETL replaces rows rather than duplicating them. `make refresh` can safely run
on a schedule.

### `data/` — everything that is data

Kept strictly separate from code. The seed CSVs are committed because they are
small and make the project runnable on a fresh clone. Two things are **not**
committed:

- `gbd.db` is a build artefact. Regenerate it any time with `make seed`.
- `incoming/*.csv` are IHME exports — large, and their redistribution is
  governed by IHME's data terms.

### `static/` — the frontend

One self-contained `index.html`. No build step, no `npm install`, no bundler:
open it and it works. Chart.js is **vendored** into `assets/` rather than
loaded from a CDN, so the dashboard works on a restricted or air-gapped
network and cannot break because someone else's CDN changed.

### `tests/` — the safety net

`pytest`, run with `make test`. Tests build their own temporary database from
the real CSVs, so running them can never disturb a database you are using.

### `scripts/` and `docker/`

`scripts/refresh.sh` is the scheduled re-ingestion job, safe to run from cron.
`docker/entrypoint.sh` seeds the database on first container start — needed
because the database lives in the mounted volume, which would otherwise hide a
copy baked in at build time.

### `brand/` — source assets

Original high-resolution identity files. The versions actually served live in
`static/assets/`, cropped and sized for the web. Keeping the originals means
the web copies can be regenerated without hunting for the source again.

## How it works

### One process, one port

Early versions ran the API on `:8000` and a separate static file server on
`:8080`. That meant two processes, two ports, cross-origin requests, and a
dashboard that lived at a URL ending in `.html`. Visiting the port root gave
you a **directory listing**.

Now a single FastAPI process serves both. The benefits are practical: one
thing to start, one port to open in a firewall, no CORS round-trip, and
nothing to reconfigure when the app moves behind a UCC hostname — the frontend
calls its own origin.

### Where the database lives

`data/gbd.db`, which is **inside the volume mounted into the container**. That
is deliberate: the host and the container share one file, so running
`make refresh` on the host is visible to the running container immediately.

The trade-off is that a database baked into the image at build time would be
hidden by that mount. `docker/entrypoint.sh` handles it: on start, if the file
is not there, it seeds from the bundled CSVs and then hands over to uvicorn.
A fresh `git clone` plus `make up` therefore gives a working dashboard with no
manual step.

### What "live" honestly means

IHME does not offer a free, real-time, arbitrary-query REST API for GBD
estimates. GBD is published in **annual rounds** (GBD 2021, GBD 2023, …) as
**bulk CSV exports** via the
[GBD Results Tool](https://vizhub.healthdata.org/gbd-results/). So:

- **Dashboard → API is live.** The frontend makes real HTTP requests and always
  reflects whatever is in the database right now.
- **API → IHME is scheduled.** `make refresh` re-ingests when a new round or
  extract is downloaded. Checking monthly is more than sufficient; there is
  nothing to gain from polling more often than IHME publishes.

This is standard practice for any dashboard built on an annually-released
source, and it is the architecture recommended in the accompanying technical
specification for the Department of Health prototype.

## The API

Interactive documentation, generated from the code, is at
<http://127.0.0.1:8000/docs>.

| Endpoint | Returns |
|---|---|
| `GET /api/health` | Liveness check |
| `GET /api/meta` | GBD round and source of the current data |
| `GET /api/indicators` | Every available trend indicator |
| `GET /api/trend?indicator=tobacco_sev` | Time series for one indicator |
| `GET /api/ranked?type=causes\|risks` | Ranked causes or risk factors |
| `GET /api/export.csv?indicator=le` | CSV download, for citation and reuse |

```bash
curl http://127.0.0.1:8000/api/meta
curl "http://127.0.0.1:8000/api/trend?indicator=tobacco_sev"
```

Optional parameters `location` (default `Ireland`) and `sex` (default
`combined`) exist on the trend endpoints — the schema has been multi-location
from the start.

**Error codes are meaningful.** An unknown indicator returns `404`, not an
empty series: an empty chart looks like real data, whereas a 404 cannot be
mistaken for one. A missing database returns `503` with the command that fixes
it.

## The dashboard

- **UCC identity** — logo and a map of the Republic of Ireland with Cork marked
  on the left; principal investigator, linked to their UCC research profile, on
  the right.
- **Hero figure and stat tiles** — life expectancy leads; healthy life
  expectancy, tobacco, BMI, and air pollution follow with sparklines and
  change-since-baseline, all computed from live API responses.
- **Light and dark themes** — follows the operating system by default, with a
  toggle that remembers your choice.
- **A table view on every chart** — the same data as an accessible table, so no
  value is reachable only by hovering.

**On the chart colours.** The series palette is not hand-picked. It uses
validated categorical slots, checked in both themes for lightness band, chroma
floor, colour-vision-deficiency separation (protanopia and deuteranopia,
Machado 2009 at full severity), a normal-vision separation floor, and contrast
against the surface. Two light-mode hues sit below the 3:1 contrast line, which
is permitted only alongside a relief channel — hence the visible value labels
and the table views. UCC navy and gold are chrome only; they never encode data.

If you change a series colour, re-validate it rather than eyeballing it: a
palette that merely *looks* distinct routinely collapses under CVD simulation.

## Loading real GBD data

1. Register for and download a bulk export from the
   [GBD Results Tool](https://vizhub.healthdata.org/gbd-results/) — your
   choice of indicators, locations, and years.
2. Save it into `data/incoming/`.
3. Run `make refresh`.

The adapter maps the standard export columns (`cause_name` / `rei_name`,
`location_name`, `sex_name`, `year`, `val`, `metric_name`) onto the same schema
the seed data uses, so the API and dashboard need no changes.

**Pass an `indicator_map`.** Without one, indicator IDs are derived from IHME's
label text — so a rewording between rounds would silently create a *new*
indicator and break the dashboard's saved selection. With one, your IDs stay
stable:

```python
ingest_gbd_export(
    "data/incoming/IHME-GBD_2023_DATA.csv",
    indicator_map={"Tobacco": "tobacco_sev", "High body-mass index": "bmi_sev"},
)
```

### Scheduling it

`scripts/refresh.sh` is cron-safe — it resolves its own repository root and
uses the project virtual environment rather than the system Python:

```cron
0 3 1 * *  /path/to/ucc_gbd_pipeline/scripts/refresh.sh >> /var/log/gbd_refresh.log 2>&1
```

## Testing and code quality

```bash
make check     # lint + tests, the same checks CI runs
```

- **`make test`** — pytest. The API tests pin down every endpoint's contract:
  response shape, ordering guarantees, and error codes. The ETL tests cover
  idempotency, the real-export column mapping, stable indicator IDs, and that
  one malformed row does not abort an otherwise good import.
- **`make lint`** — [ruff](https://docs.astral.sh/ruff/), for both style and
  formatting. `make format` fixes what can be fixed automatically.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the same
  checks on every push and pull request, **plus** a real container build that
  starts the image and smoke-tests it — so a change cannot merge if it only
  works on one machine.

## Deployment

`docker compose up -d` runs this as-is on:

- A UCC IT-provisioned Linux VM with Docker — the most straightforward route,
  and a common, low-overhead request for a research group.
- UCC's research computing environment, if it supports containerised services.
- A low-cost external host (Fly.io, Render) for a public-facing demo, if data
  governance permits.

The container runs as a **non-root user** and declares a **healthcheck**, so an
orchestrator can tell readiness from "the process started".

**Before exposing this beyond a trusted network**, add authentication — an API
key or UCC SSO check in `app/main.py`. There is none today: every endpoint is
public and read-only by design.

## Configuration

Every setting is an environment variable with a sensible default, so nothing
below is required to run the project.

| Variable | Default | What it does |
|---|---|---|
| `GBD_DATA_DIR` | `<repo>/data` | Directory holding the CSVs and the database |
| `GBD_DB_PATH` | `<GBD_DATA_DIR>/gbd.db` | The SQLite database file |
| `GBD_STATIC_DIR` | `<repo>/static` | Frontend files served at `/` |
| `GBD_ROUND` | `GBD 2023` | Label recorded against ingested rows |

## Troubleshooting

**"Port already in use"** — `make status` shows what is holding port 8000. Use
`make stop` for a local process and `make down` for the container. Killing a
PID from `lsof` while Docker is running fights the Docker proxy rather than
stopping the container.

**The dashboard says the API is unreachable** — the app is not running. Start
it with `make run` or `make up`, then confirm with `make smoke`.

**A `503` mentioning the database** — the ETL has not run. `make seed` builds
it; `make reseed` rebuilds from scratch.

**Charts are empty after loading a real export** — check the indicator IDs. Run
`curl http://127.0.0.1:8000/api/indicators`; if they look like slugified IHME
label text, supply an `indicator_map` (see
[Loading real GBD data](#loading-real-gbd-data)).

**Something is deeply wrong** — `make clean` removes the database, logs, and
caches without touching `.venv`. `make distclean` also removes `.venv`. Then
`make setup && make run`.

## Data governance and attribution

IHME's GBD data is free to use with attribution under IHME's
[Free-to-Use Data Terms](https://www.healthdata.org/gbd/about/data-terms).
Before any **public-facing** deployment, as opposed to internal research use,
confirm:

- The citation IHME requires is included. The source and round are exposed at
  `/api/meta` and shown in the dashboard footer.
- Whether your use counts as "redistribution" under IHME's terms. Serving
  pre-aggregated indicators through this API is generally consistent with
  permitted use, but the terms are IHME's to set and can change — check the
  current version before any wider release.
- UCC's own research data management policy, if hosting externally.

The UCC logo and the identity assets in `brand/` are University College Cork
marks. Check UCC's brand guidelines before publishing anything outward-facing
under them.

---

<div align="center">

**Not for clinical or diagnostic use.**

School of Public Health · University College Cork · Cork, Ireland

</div>
