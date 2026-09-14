<div align="center">

# Global Health Evidence

**A secure, multi-country ETL → API → dashboard pipeline for Global Burden of Disease indicators, launching with Ireland**

School of Public Health · University College Cork · Cork, Ireland

`Python 3.11+` · `FastAPI` · `SQLite` · `Docker` · `GitHub Pages` · `no frontend build step`

**[Public landing page →](https://abdulrazakucc.github.io/ireland-gbd-dashboard/)** · results are available to approved users only

[![CI](https://github.com/abdulrazakucc/ireland-gbd-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/abdulrazakucc/ireland-gbd-dashboard/actions/workflows/ci.yml)
[![Pages](https://github.com/abdulrazakucc/ireland-gbd-dashboard/actions/workflows/pages.yml/badge.svg)](https://github.com/abdulrazakucc/ireland-gbd-dashboard/actions/workflows/pages.yml)

</div>

---

**Principal Investigator and Public Health Lead** — [Dr. Zubair Kabir](https://research.ucc.ie/en/persons/zubair-kabir/),
Senior Lecturer, School of Public Health, University College Cork.

**Technical Lead, Lead Developer and Applied AI/Data Science Lead** — Abdul Razak, PhD.

---

## Table of contents

- [GitHub Pages](#github-pages)
- [What this is](#what-this-is)
- [Research and Technical Leadership](#research-and-technical-leadership)
- [Before you start](#before-you-start)
- [Quick start](#quick-start)
- [Accounts and sign-in](#accounts-and-sign-in)
- [All commands](#all-commands)
- [Everyday recipes](#everyday-recipes)
- [Repository structure](#repository-structure)
- [What each directory is for](#what-each-directory-is-for)
- [How it works](#how-it-works)
- [The API](#the-api)
- [The application](#the-application)
- [Loading real GBD data](#loading-real-gbd-data)
- [Testing and code quality](#testing-and-code-quality)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Data governance and attribution](#data-governance-and-attribution)
- [Security policy](SECURITY.md)

---

## GitHub Pages

**<https://abdulrazakucc.github.io/ireland-gbd-dashboard/>**

GitHub Pages republishes on every push to `main`. A static site cannot check who
is asking — every file there can be downloaded by anyone — so it publishes one
of two shapes:

| Repository secret `GBD_USERS_JSON` | What is published |
|---|---|
| Not set | The public **landing page** only |
| Set | The landing page **and the application**, with every result **encrypted** |

With accounts, `scripts/build_static_site.py` collects every response the
application can show, encrypts them with AES-256-GCM under a new key on every
build, and wraps that key for each account with the account's password hash.
Signing in on the published page re-derives that hash **in the browser** and
decrypts the results there: no server is involved, and nothing is readable
without a valid email and password. No email address, name or password hash is
published.

**To let someone sign in to the published copy** — for example for a presentation:

```bash
make user-add EMAIL=someone@example.org NAME="Their Name"   # asks for the password
make user-export                                            # prints the accounts file
```

Paste that output into **Settings → Secrets and variables → Actions → New
repository secret**, name it `GBD_USERS_JSON`, and re-run the *Deploy site to
GitHub Pages* workflow. To remove access, run `make user-remove`, update the
secret and re-run: the next copy uses a new key the removed account cannot open.

**Limits of the published copy** — read these before relying on it:

- Anyone can download the encrypted files and try passwords offline. Use a long,
  unique password for these accounts (12 characters is the minimum, not a target).
- Removing an account protects the copies built afterwards, not earlier ones.
- It suits a handful of named accounts. For many users, run the application on
  a server: same sign-in screen, same accounts, no offline guessing.

Preview exactly what Pages will serve:

```bash
make site-serve     # sealed for data/access/users.json if it exists; serves on :8001
```

## What this is

Ireland is the first loaded dataset, not a hard-coded boundary. `location` is
part of every series key, filter, ranking and export, so adding approved country
files through the same ETL automatically adds them to the interface. Headline
copy adapts to one or many loaded locations.

Three pieces that fit together:

```text
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

## Research and Technical Leadership

**Dr. Zubair Kabir — Principal Investigator and Public Health Lead**

Provides the project's public-health leadership, GBD expertise, research
direction, interpretation, data stewardship and institutional coordination.

**Abdul Razak, PhD — Technical Lead, Lead Developer and Applied AI/Data Science Lead**

Leads the end-to-end design and implementation of the software platform,
including system architecture, data-ingestion and validation pipelines, API and
dashboard development, statistical forecasting, secure-access controls,
automated testing, reproducibility, technical documentation and deployment
engineering. He also leads the planned development and validation of
machine-learning forecasting and Bayesian decision-support capabilities.

Machine-learning forecasting and Bayesian decision support are **planned work**
and are not part of the current application, whose forecasts are exploratory
linear trends. [CONTRIBUTORS.md](CONTRIBUTORS.md) describes both roles in more
detail.

### Authorship and citation

Global Health Evidence is developed at the School of Public Health, University
College Cork. To cite the software, use [CITATION.cff](CITATION.cff); GitHub
also offers it as **Cite this repository** on the repository page. Cite the GBD
estimates themselves with the IHME citation the application shows alongside
the data and draws on every downloaded figure.

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

```text
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
cd path/to/ireland-gbd-dashboard
```

You are in the right place if `ls` shows a `Makefile`.

## Quick start

> **On Windows, or new to the command line?** Unzip the project and
> **double-click [`Install.cmd`](Install.cmd)**. That is the whole
> installation — no terminal, no typing, no admin rights. It uses Docker if
> the machine already has it running, otherwise installs Python via pyenv into
> the user's own profile, builds the database, starts the app, and adds a
> Desktop shortcut. See **[INSTALL_WINDOWS.md](INSTALL_WINDOWS.md)** for the
> full non-technical guide, including a Mac section.

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
| **Website** | <http://127.0.0.1:8000> |
| **Application** | <http://127.0.0.1:8000/app/> — sign in here |
| **JSON API** | <http://127.0.0.1:8000/api/...> — for signed-in users |

**Before you sign in the first time, create your account:**

```bash
make user-add EMAIL=you@example.org NAME="Your Name"
```

Without `make` (for example on Windows): `python -m app.accounts add you@example.org`.
In Docker: `docker compose exec app python -m app.accounts add you@example.org`.

There is no separate frontend server and no HTML file to open by hand. Confirm
everything is working with `make smoke`.

To stop: `make down` (Docker) or `make stop` (local).

## Accounts and sign-in

Everything that shows results requires signing in — on a laptop, on a server and
on the GitHub Pages copy — through the same screen, with the same accounts.

```bash
make user-add EMAIL=someone@example.org NAME="Their Name"   # create, or set a new password
make user-list                                              # who can sign in
make user-remove EMAIL=someone@example.org                  # revoke, immediately
```

The password is typed at a hidden prompt and never stored:
`data/access/users.json` keeps a salted PBKDF2-HMAC-SHA256 hash (600,000
iterations), is git-ignored, never copied into an image, and readable only by
its owner. A session is a signed, expiring cookie that page scripts cannot
read; removing an account or changing its password ends its sessions at once,
and repeated failed sign-ins are slowed down. See [SECURITY.md](SECURITY.md).

**Growing to thousands of users.** The password format, the sign-in screen and
the session design carry over unchanged. The next steps are moving accounts
from the file into a database with access requests and an approval queue, and
moving the sign-in rate limit to a shared store so several server processes can
enforce it together. Single sign-on through UCC's identity provider is already
possible: set `GBD_AUTH_MODE=proxy` behind an identity-aware reverse proxy.

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
| `make seed` | Build the database from the seed data — only if there is no usable one, so it never replaces a real import |
| `make reseed` | Replace the database with the seed data (the old one is kept as `data/gbd.db.previous`) |
| `make run` | Start the app in the background |
| `make stop` | Stop it |
| `make restart` | Stop, then start |
| `make status` | Show what is listening on the port |
| `make open` | Open the application in a browser |
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
| `make audit` | Check runtime dependencies for known vulnerabilities |
| `make format` | Auto-fix formatting and import order |
| `make smoke` | Check a **running** app answers on every endpoint |
| `make check` | `lint` + `test` — exactly what CI runs |

### Data and housekeeping

| Command | What it does |
|---|---|
| `make refresh` | Import the newest GBD export from `data/incoming/` — validated, built and verified before it replaces anything |
| `make clean` | Remove the database, logs, and caches (keeps `.venv`) |
| `make distclean` | Also remove `.venv` |

### Accounts

| Command | What it does |
|---|---|
| `make user-add EMAIL=…` | Create an account, or set a new password (hidden prompt) |
| `make user-list` | List who can sign in |
| `make user-remove EMAIL=…` | Remove an account; its sessions end at once |
| `make user-export` | Print the accounts file, for the `GBD_USERS_JSON` GitHub secret |

## Everyday recipes

Find what you want to do, then run the command beside it.

| I want to… | Command |
|---|---|
| Run it for the very first time | `make dev`, then `make user-add EMAIL=…` |
| Let someone sign in | `make user-add EMAIL=…` |
| Give someone access to the GitHub Pages copy | `make user-add`, then update the secret with `make user-export` |
| Start it again tomorrow | `make start` |
| Stop it | `make stop` |
| See it in my browser | `make open` |
| Find out which address it is on | `make urls` |
| Check whether it is actually working | `make smoke` |
| See what the app is doing right now | `make logs` *(press `Ctrl+C` to stop watching)* |
| Find out why it will not start | `make doctor`, then `make status` |
| Pick up my changes to the frontend | Just refresh the browser — no restart needed |
| Pick up my changes to Python code | `make restart` |
| Load a new GBD export | Put the CSV in `data/incoming/`, then `make refresh` |
| Rebuild the database from scratch | `make reseed` |
| Check my changes did not break anything | `make check` |
| Tidy up formatting before committing | `make format` |
| Start completely fresh | `make distclean` then `make dev` |

### A first session, start to finish

```bash
cd path/to/ireland-gbd-dashboard

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

```text
ireland-gbd-dashboard/
│
├── app/                          The web application (API, sign-in, serves the site)
│   ├── __init__.py
│   ├── config.py                 Every path and setting, resolved once
│   ├── accounts.py               Accounts: password hashing, users file, CLI
│   ├── auth.py                   Sign-in: sessions, rate limiting, /api/auth routes
│   ├── db.py                     The database schema, and SQLite access
│   ├── queries.py                Every read, shared by the API, figures and import checks
│   ├── gbd.py                    GBD rules: units, display scaling, citation
│   ├── figures.py                PNG and PDF figures, with GBD context drawn on
│   ├── schemas.py                Response models: the API's contract
│   ├── routes.py                 The /api routes
│   └── main.py                   App factory: security headers, sign-in guard, serves static/
│
├── etl/                          Getting data INTO the database
│   ├── __init__.py
│   ├── gbd_import.py             validate -> build new database -> verify -> activate
│   └── load_seed.py              Command line: seed, import an export, --ensure
│
├── data/                         All data lives here (never in the code dirs)
│   ├── gbd_seed.csv              Prototype seed data, in GBD Results Tool format
│   ├── gbd.db                    SQLite database — BUILT, not committed
│   ├── gbd.db.previous           The database the last import replaced — not committed
│   ├── access/                   Accounts (users.json) — never committed
│   └── incoming/                 Drop new GBD Results Tool exports here
│
├── site/                         The GitHub Pages site — BUILT, not committed
│
├── static/                       The frontend — no build step
│   ├── index.html                Public landing page, served at /
│   ├── app/                      The application, served at /app/
│   │   ├── index.html            Application shell (no inline scripts)
│   │   ├── app.css               Design system: layout, components, themes
│   │   ├── config.js             "server" locally; "sealed" in the Pages copy
│   │   └── js/                   Modules: main, api, sealed, charts, login, present
│   │       └── views/            One module per view: overview, trends, rankings, methods
│   └── assets/
│       ├── ucc-logo.png          Cropped, web-sized UCC logo
│       ├── zubair-kabir.png      Principal investigator photograph
│       └── chart.umd.js          Chart.js, vendored — no CDN dependency
│
├── tests/                        Test suite (pytest)
│   ├── conftest.py               Fixtures: seed and synthetic multidimensional databases
│   ├── test_api.py               Every endpoint's contract, CORS, database errors
│   ├── test_auth.py              Accounts, sessions, what signed-out visitors can reach
│   ├── test_api_filters.py       Filters on every dimension, rankings, CSV export
│   ├── test_figures.py           PNG and PDF exports and the context they carry
│   ├── test_import.py            Dimensions kept apart, intervals, duplicates, rollback
│   ├── test_etl.py               The seed loads through the real importer
│   └── test_static_site.py       GitHub Pages: landing only, or a copy only credentials open
│
├── scripts/
│   ├── build_static_site.py      Builds the GitHub Pages site, sealing results for accounts
│   ├── refresh.sh                Safe re-import of a new export (cron-friendly)
│   └── install.ps1               One-command Windows setup, no admin rights
│
├── docker/
│   └── entrypoint.sh             Ensures a usable database on container start
│
├── brand/                        Original high-resolution identity assets
│   ├── ucc-logo.png              Source logo (the web copy is in static/assets)
│   └── zubair-kabir.png          Source photograph
│
├── .github/workflows/
│   ├── ci.yml                    Lint, test, and a real container build
│   └── pages.yml                 Builds and publishes the site to GitHub Pages
│
├── Install.cmd                   Windows one-click setup (double-click it)
├── Makefile                      Every command for this project
├── Dockerfile                    Container image definition
├── docker-compose.yml            One service, one port
├── requirements.txt              Runtime dependencies, pinned
├── requirements-dev.txt          Test and lint dependencies, pinned
├── pyproject.toml                ruff and pytest configuration
├── .env.example                  Optional settings; copy to .env (never committed)
├── .gitignore                    Build artefacts, licensed data and secrets stay out
├── .dockerignore                 Keeps the image small and clean
├── CITATION.cff                  How to cite this software
├── CONTRIBUTORS.md               Research and technical leadership roles
├── SECURITY.md                   Security and privacy policy
└── README.md                     This file
```

## What each directory is for

### `app/` — the web application

The API and the dashboard are served by **one** FastAPI application on **one**
port. The package is split by responsibility so each file has one job:

| File | Responsibility |
|---|---|
| `accounts.py` | Who may sign in: the users file, PBKDF2 password hashing, and the `add` / `remove` / `list` commands. |
| `auth.py` | Signing in: signed session cookies re-checked on every request, the sign-in rate limit, and the `/api/auth` routes. |
| `config.py` | The single source of truth for **where things are**. Nothing else in the codebase works out a path by walking `__file__`. Every path can be overridden with an environment variable, which is how Docker and the tests point the app elsewhere without editing code. |
| `db.py` | The database schema and its version, and opening connections. The importer that writes the format and the API that reads it share this one definition. |
| `queries.py` | Every read the application makes. The routes, the figure renderer and the importer's verification step all call these, so a selection has exactly one answer wherever it is asked. |
| `gbd.py` | GBD rules in one place: what each metric's unit is, how a value is scaled for display, and how a release is cited. |
| `figures.py` | Renders one series as a PNG or PDF with its release, every dimension, uncertainty, forecast disclosure, IHME citation, de-identified provenance and import date. Uses matplotlib's object API, never `pyplot`, which is not thread-safe. |
| `schemas.py` | Pydantic models describing every response. They define the API's contract, give the frontend a contract, and make a shape change fail loudly in tests. |
| `routes.py` | The `/api` endpoints. Thin: each one is a query from `queries.py` plus HTTP error handling. |
| `main.py` | Builds the application — security headers, the sign-in guard in front of `/api`, routes, and the static mount. |

**One ordering rule matters here.** The dashboard is mounted at `/`, which is a
catch-all. FastAPI matches routes in declaration order, so the `/api` router is
registered **before** the static mount. Reverse them and every API call would
return the HTML page instead. `tests/test_api.py` guards this.

### `etl/` — getting data in

Every load — the bundled seed included — goes through one pipeline in
`gbd_import.py`:

**new file → validate → build new database → verify → activate**

The live database is never written to in place. A complete new database is
built beside it, checked, and only then swapped in with an atomic rename. If
any step fails, the dashboard keeps serving exactly what it served before and
no half-built file is left behind. See [Loading real GBD data](#loading-real-gbd-data).

`load_seed.py` is the command line over it: no arguments loads the seed,
`--gbd-export` imports an IHME export, and `--ensure` builds a database only
when there is no usable one (what `make seed` and the container run).

### `data/` — everything that is data

Kept strictly separate from code. The seed CSV is committed because it is
small and makes the project runnable on a fresh clone. It is in the same GBD
Results Tool format as a real export, so it is validated by the same importer.
Three things are **not** committed:

- `gbd.db` is a build artefact. Regenerate it any time with `make seed`.
- `gbd.db.previous` is the database the last successful import replaced.
- `incoming/*.csv` are IHME exports — large, and their redistribution is
  governed by IHME's data terms.

### `static/` — the frontend

Two parts, and still no build step, no `npm install` and no bundler:

- `index.html` — the public landing page.
- `app/` — the application: a small shell page, one stylesheet, and plain
  JavaScript modules. `js/main.js` registers the views; adding an analysis means
  writing one module in `js/views/` and listing it there. `js/api.js` gives every
  view the same data interface, whether results come from the server or from the
  sealed copy on GitHub Pages.

Chart.js is **vendored** into `assets/` rather than loaded from a CDN, so the
application works on a restricted or air-gapped network, and every script is a
file served by the site itself, so the Content-Security-Policy permits no inline
or third-party scripts.

### `tests/` — the safety net

`pytest`, run with `make test`. Tests build their own temporary databases — the
real seed, and a synthetic export with several measures, metrics, ages, sexes,
causes, risks and uncertainty intervals at once — so running them can never
disturb a database you are using.

### `scripts/` and `docker/`

`scripts/refresh.sh` imports a new export through the safe pipeline and exits
non-zero, leaving the live database untouched, if the import is refused. It is
safe to run from cron. `docker/entrypoint.sh` makes sure a usable database
exists on container start: it seeds one if there is none and rebuilds an
old-format copy of the seed, but refuses to replace a real import — needed
because the database lives in the mounted volume, which would otherwise hide a
copy baked in at build time.

`scripts/build_static_site.py` builds the [GitHub Pages site](#github-pages).
Without accounts it publishes the landing page and its images; with accounts it
adds the application and every result it can show, encrypted so that only those
accounts can open them. Either way it writes only allow-listed files and refuses
to publish if any readable result, email address or name would leave the
ciphertext, because every file on GitHub Pages is public.

`scripts/install.ps1` is the one-command Windows installer described in
[INSTALL_WINDOWS.md](INSTALL_WINDOWS.md), and `Install.cmd` at the repository
root is the double-click wrapper for it. It targets people who do not have
administrator rights: it prefers Docker when the machine already has it
running, and otherwise installs Python through pyenv into the user's own
profile. It is idempotent — re-running it resumes rather than restarts.

The wrapper exists because Windows refuses to run a `.ps1` on double-click.
`Install.cmd` invokes PowerShell with `-ExecutionPolicy Bypass`, which is
scoped to that one child process: it changes no machine setting and needs no
elevation.

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
hidden by that mount. `docker/entrypoint.sh` handles it: on start it runs
`python -m etl.load_seed --ensure`, which seeds a database if there is none,
rebuilds an old-format copy of the seed data, and otherwise leaves the database
alone, then hands over to uvicorn. A fresh `git clone` plus `make up`
therefore gives a working dashboard with no manual step.

The app opens the database per request, so after an import it serves the new
data from the very next request, with no restart.

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

Interactive documentation (`/docs`, `/openapi.json`) is **off by default**, in
every environment, so the application does not publish a map of its endpoints.
For local development only, set `GBD_EXPOSE_DOCS=true`.

Every estimate keeps all of its GBD dimensions — **release, measure, metric,
location, sex, age, cause, risk and year** — with its value and 95%
uncertainty interval (`lower`, `upper`). Start from what exists, then read it:

| Endpoint | Returns |
|---|---|
| `GET /api/health` | Liveness check |
| `GET /api/meta` | Release, import date, de-identified source labels with row counts, citation |
| `GET /api/dimensions` | The values available for every dimension, narrowed by any filters given |
| `GET /api/series` | The catalogue: one entry per series (every dimension but year) and its years |
| `GET /api/trend?series=ID` | One series over time, with intervals and optional forecast |
| `GET /api/estimates` | Flat rows for any selection, paged with `limit` and `offset` |
| `GET /api/ranked?type=causes\|risks` | Causes or risks ranked high to low, with optional projected ranking |
| `GET /api/ranked/options` | Every selection a ranking can be drawn for |
| `GET /api/export.csv` | CSV of a series or a selection: every dimension, value and interval |
| `GET /api/figure.png`, `GET /api/figure.pdf` | A figure of one series with its GBD context and citation |

**Filters** mean the same thing on every endpoint that takes them: `release`,
`measure`, `metric`, `location`, `sex`, `age`, `cause`, `risk`, `year_from`
and `year_to`. Values match exactly what `/api/dimensions` lists. For `cause`
and `risk`, an empty value (`risk=`) selects rows where the dimension does not
apply — life expectancy has neither.

```bash
curl "http://127.0.0.1:8000/api/dimensions?measure=Deaths"
curl "http://127.0.0.1:8000/api/trend?measure=Deaths&metric=Rate&age=Age-standardized&sex=Both&cause=Lung%20cancer&risk=&year_from=2010"
curl "http://127.0.0.1:8000/api/trend?series=<series_id>&forecast_years=5"
curl -o figure.pdf "http://127.0.0.1:8000/api/figure.pdf?series=<series_id>"
```

**Error codes are meaningful.** A selection that matches nothing returns `404`,
not an empty series: an empty chart looks like real data, whereas a 404 cannot
be mistaken for one. A selection that matches **more than one** series or
ranking returns `409`, listing the dimensions that still vary — the API never
guesses which age or metric you meant. A missing or out-of-date database
returns `503` with the command that fixes it.

**Rankings.** Causes are ranked without the `All causes` total; risks are
ranked on their all-cause burden, or on their exposure where there is no cause.
GBD causes are hierarchical, and an export may mix levels, in which case a
parent such as *Mental disorders* is ranked alongside its own sub-causes. The
dashboard says so under the chart; download a single cause level to compare
like with like.

**Percent** values are stored as IHME exports them, as proportions (`0.12` =
12%). The API reports a `display_scale` of 100 for them, which the dashboard and
figures apply; CSV downloads keep the stored values.

**Forecasts are opt-in.** Add `forecast_years=3`, `5`, or up to `10` to trend,
ranking, CSV, PNG or PDF requests. The service fits a reproducible ordinary
least-squares trend to up to the latest 15 observations, requires at least
three distinct annual observations, and returns an approximate 95% prediction
interval. Observed and projected values remain separate, and projections are
never stored in the source database. They are exploratory analytical aids—not
clinical predictions or replacements for an epidemiological model.

**CORS is off by default.** The dashboard is same-origin, and notebooks, R and
`curl` do not use CORS. If a separate web app must call the API from a browser,
list its origin in `GBD_CORS_ORIGINS` — never `*`.

## The application

A single-page application with a sidebar of views. On a laptop or desktop, each
view fits the screen: readers click between views instead of scrolling.

- **Sign-in** — the same screen locally, on a server and on GitHub Pages.
- **Overview** — life expectancy leads, with its trend and exploratory outlook;
  healthy life expectancy, tobacco, BMI and air pollution follow with
  sparklines; highlights and the leading causes complete the picture. Every card
  opens the detailed view on exactly what it summarises.
- **Trends** — one series at a time, chosen by measure, cause, risk, metric,
  age, sex and year range. Choices only offer combinations that exist, so none
  is a dead end. The 95% uncertainty interval is drawn as a band; an optional 3-,
  5- or 10-year exploratory forecast is dashed, with its prediction interval and
  method stated beside it.
- **Rankings** — the leading causes or risk factors for a population and year,
  with the top three and an optional projection.
- **Methods & data** — the IHME citation with a copy button, the dataset's
  provenance, and how to read uncertainty intervals and forecasts.
- **Present** — full-screen slides built from the loaded data: title, life
  expectancy, headline indicators, leading causes and risks, the trend last
  selected, and sources. Arrow keys move between slides, `F` toggles full
  screen, `Esc` closes, and `P` opens it from any view.
- **Downloads** — CSV, PNG and PDF of exactly the current selection. Figures
  carry the release, every dimension, the IHME citation and the import date, and
  mark prototype data as not for citation. The GitHub Pages copy offers CSV and
  PNG, generated in the browser.
- **Shareable views** — the address records the view and selection, so a link
  reopens the same chart after signing in.
- **Light and dark themes**, and a **table view** on every chart, so no value is
  reachable only by hovering.

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

1. Download an export from the
   [GBD Results Tool](https://vizhub.healthdata.org/gbd-results/) — any
   measures, metrics, ages, sexes, causes, risks, locations and years. Both
   download styles work: "ID and name" (`measure_name`, `rei_name`, …) and
   "name only" (`measure`, `rei`, …).
2. Save it into `data/incoming/`.
3. Run `make refresh`. For a download the Results Tool split into parts, name
   them all: `scripts/refresh.sh data/incoming/part-1.csv data/incoming/part-2.csv`.

Every import follows **new file → validate → build new database → verify →
activate**:

| Step | What happens |
|---|---|
| **Validate** | Required columns (`measure`, `metric`, `location`, `sex`, `age`, `year`, `val`) are present and unambiguous; every row has them; years and values are numbers; intervals are valid; `Percent` values are proportions. Common patient, participant, contact, credential and direct-identifier columns are prohibited. **One invalid row refuses the whole import.** |
| **Detect duplicates** | Two rows for the same release, measure, metric, location, sex, age, cause, risk and year would overwrite one another. The import is refused, listing each duplicate, whether its copies are identical or conflicting, and the file and line of every copy. |
| **Build** | A complete new database is written beside the live one, with its provenance: release, import time, source, row count, and each file's name, size, row count and SHA-256 checksum. |
| **Verify** | SQLite integrity check, schema version, every row and file accounted for, and the series catalogue read back through the same queries the API uses. |
| **Activate** | The live database is copied to `data/gbd.db.previous`, then replaced by an atomic rename. The running app serves the new data from its next request. |

A failure at any step exits non-zero with the reason and leaves the live
database **byte-for-byte unchanged**, with no leftover files.

**The release** comes from `--release`, otherwise from the filename
(`IHME-GBD_2021_DATA-….csv` gives `GBD 2021`), otherwise from `GBD_ROUND`. A
`--release` that contradicts the filename is refused rather than mislabelling
every figure:

```bash
python -m etl.load_seed --gbd-export data/incoming/export.csv --release "GBD 2023"
```

**To undo an import**, put the previous database back:
`mv data/gbd.db.previous data/gbd.db`.

**Check the first real export.** The importer follows IHME's published export
format and is tested with synthetic files in that format, but this repository
holds no real export to test against. When the first real download arrives,
import it and look at `/api/dimensions` before relying on it.

### Scheduling it

`scripts/refresh.sh` is cron-safe — it resolves its own repository root and
uses the project virtual environment rather than the system Python:

```cron
0 3 1 * *  /path/to/ireland-gbd-dashboard/scripts/refresh.sh >> /var/log/gbd_refresh.log 2>&1
```

## Testing and code quality

```bash
make check     # lint + tests + dependency audit, the same checks CI runs
```

- **`make test`** — pytest. The API tests pin down every endpoint's contract:
  response shape, ordering, filters on every dimension, and error codes. The
  import tests prove that estimates differing by measure, metric, age, sex,
  cause or risk cannot overwrite one another, that uncertainty intervals
  survive, that duplicates and invalid rows are refused, and that **a failed
  import leaves the live database byte-for-byte unchanged**. The figure tests
  check that PNG and PDF downloads are real files carrying their release and
  citation.
- **`make lint`** — [ruff](https://docs.astral.sh/ruff/), for both style and
  formatting. `make format` fixes what can be fixed automatically.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the same
  checks on every push and pull request, **plus** a real container build that
  starts the image and smoke-tests it — so a change cannot merge if it only
  works on one machine.

## Deployment

There are two deployments, and they serve different purposes.

### GitHub Pages

**<https://abdulrazakucc.github.io/ireland-gbd-dashboard/>** — the landing page
and, when the `GBD_USERS_JSON` secret is set, the sealed application for the
accounts in it (see [GitHub Pages](#github-pages)). It needs no server. Pushing to
`main` runs `.github/workflows/pages.yml`, which runs the tests, builds the site,
refuses to publish anything readable beyond the landing page, and deploys it.

One-time setup, already done: **Settings → Pages → Source: GitHub Actions**.

### The live application

`docker compose up -d` runs this as-is on:

- A UCC IT-provisioned Linux VM with Docker — the most straightforward route,
  and a common, low-overhead request for a research group.
- UCC's research computing environment, if it supports containerised services.
- A low-cost external host (Fly.io, Render) for a public-facing demo, if data
  governance permits.

The container runs as a **non-root user** and declares a **healthcheck**, so an
orchestrator can tell readiness from "the process started".

Production access is fail-closed. With `GBD_ENV=production`, startup is refused
unless sign-in is enforced: either `GBD_AUTH_MODE=password` with a session secret
of at least 32 characters (preferably the mounted file named by
`GBD_SESSION_SECRET_FILE`), or `GBD_AUTH_MODE=proxy` with a proxy secret
(preferably through `GBD_PROXY_SECRET_FILE`). Serve password sign-in over HTTPS;
its cookies are marked `Secure` in production. For proxy mode, an
identity-aware reverse proxy must remove inbound authentication headers,
authenticate the approved user, then set `X-Forwarded-User` and
`X-GBD-Proxy-Secret` on the private upstream request. Keep the app port private
to that proxy and terminate HTTPS there. API documentation is disabled in
production by default.

Every response also receives a restrictive content-security policy,
anti-framing, MIME-sniffing, referrer and browser permissions headers; API
responses use `Cache-Control: no-store`, and production adds HSTS. Uvicorn's
version-bearing `Server` header is disabled in the supplied launch commands.

## Configuration

Every setting is an environment variable with a sensible default, so nothing
below is required to run the project.

| Variable | Default | What it does |
|---|---|---|
| `GBD_DATA_DIR` | `<repo>/data` | Directory holding the CSVs and the database |
| `GBD_DB_PATH` | `<GBD_DATA_DIR>/gbd.db` | The SQLite database file |
| `GBD_STATIC_DIR` | `<repo>/static` | Frontend files served at `/` |
| `GBD_BIND_ADDRESS` | `127.0.0.1` | Host interface used by Docker; loopback prevents accidental LAN exposure |
| `GBD_ROUND` | `GBD 2023` | Release for an import when neither `--release` nor the filename names one |
| `GBD_CORS_ORIGINS` | *(none)* | Comma-separated browser origins allowed to call the API from another site |
| `GBD_ENV` | `development` | Set `production` to enable fail-closed deployment checks and HSTS |
| `GBD_TRUSTED_HOSTS` | localhost/test hosts | Allowed HTTP Host values |
| `GBD_AUTH_MODE` | `password` | `password` (accounts file), `proxy` (identity-aware reverse proxy) or `off` (automated tests only; refused in production) |
| `GBD_USERS_FILE` | `<GBD_DATA_DIR>/access/users.json` | Accounts for password sign-in |
| `GBD_SESSION_SECRET_FILE` | *(none)* | Preferred mounted file holding the session-signing secret; required in production for password sign-in |
| `GBD_SESSION_SECRET` | *(none)* | Fallback; 32+ unpredictable characters. Without either in development, sessions end when the app restarts |
| `GBD_SESSION_HOURS` | `12` | How long a sign-in lasts |
| `GBD_PROXY_SECRET_FILE` | *(none)* | Preferred mounted file containing the proxy-to-app secret |
| `GBD_PROXY_SECRET` | *(none)* | Non-container fallback; must be 32+ unpredictable characters, while a file avoids process/container inspection |
| `GBD_AUTH_USER_HEADER` | `X-Forwarded-User` | Authenticated identity header set by the trusted proxy |
| `GBD_EXPOSE_DOCS` | off | Set `true` to serve `/docs` and `/openapi.json` during local development |

To set any of them, copy `.env.example` to `.env`. `make run` and `make up` both
read it; `.env` is git-ignored and never copied into the image.

## Troubleshooting

**"Port already in use"** — `make status` shows what is holding port 8000. Use
`make stop` for a local process and `make down` for the container. Killing a
PID from `lsof` while Docker is running fights the Docker proxy rather than
stopping the container.

**The application says the server is unreachable** — the app is not running.
Start it with `make run` or `make up`, then confirm with `make smoke`.

**"No accounts exist yet" when signing in** — create one:
`make user-add EMAIL=you@example.org` (or `python -m app.accounts add you@example.org`).

**"Too many attempts"** — sign-in pauses for that account or computer after
repeated failures. Wait fifteen minutes, or restart the app.

**The GitHub Pages copy says the email or password is incorrect** — the copy is
sealed for the accounts in the `GBD_USERS_JSON` secret when it was built. After
`make user-add`, update the secret with `make user-export` and re-run the
Pages workflow.

**A `503` mentioning the database** — either none has been built (`make seed`),
or it was built by an older version of this project (`make reseed` for seed
data, `make refresh` to re-import a GBD export). When an old-format database
holds a real import, the container stops with that message instead of
replacing it with seed data.

**`make refresh` says the import failed** — nothing was changed. The message
lists each problem with its file and line. The usual causes are a file from a
different tool (column names), two overlapping downloads imported together
(duplicates), or a `--release` that contradicts the filename.

**A `409` from the API** — the selection matches more than one series or
ranking. The response lists the dimensions that still vary; add those filters.

**The container exits saying `/srv/data` is not writable** — start it with
`make up` rather than `docker compose up`. The database lives in the bind-mounted
`data/` directory, so the container has to write into a host folder whose
ownership the image cannot change; `make up` runs it as your own user (`id -u`).
If you must call compose directly, do the same:

```bash
GBD_UID=$(id -u) GBD_GID=$(id -g) docker compose up -d --build
```

This bites on Linux only. Docker Desktop on macOS and Windows translates file
ownership, so a mismatched user goes unnoticed there.

**Something is deeply wrong** — `make clean` removes the database, logs, and
caches without touching `.venv`. `make distclean` also removes `.venv`. Then
`make setup && make run`.

## Data governance and attribution

IHME's GBD data is free to use with attribution under IHME's
[Free-to-Use Data Terms](https://www.healthdata.org/gbd/about/data-terms).
Before any **public-facing** deployment, as opposed to internal research use,
confirm:

- The citation IHME requires is included. It is served at `/api/meta`, shown in
  the dashboard footer, and drawn on every downloaded figure.
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

Technical architecture, data science and application development led by Abdul Razak, PhD.

</div>
