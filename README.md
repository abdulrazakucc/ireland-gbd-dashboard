<div align="center">

# Ireland GBD Dashboard

**A live ETL → API → dashboard pipeline for Global Burden of Disease indicators for Ireland**

School of Public Health · University College Cork · Cork, Ireland

`FastAPI` · `SQLite` · `pandas` · `Docker`

</div>

---

A real, working pipeline serving Global Burden of Disease indicators for
Ireland. This replaces the earlier static-HTML prototype
(`ireland_gbd_dashboard.html`) with a genuine backend serving live queries.

Tested end to end: the ETL loads real data, the API serves it, and the
dashboard renders from live HTTP calls — not embedded JavaScript arrays.

**Principal Investigator** — Dr. Zubair Kabir, Senior Lecturer,
School of Public Health, University College Cork.

---

## Quick start

Everything runs through `make`. Run `make` on its own for the full list.

```bash
make up          # Docker: build and start everything
```

```bash
make setup       # Local: create .venv and install dependencies
make run         # Local: start the app
```

Either way, one process serves everything on **one port** — no separate
frontend server, no HTML file to open by hand:

| | |
|---|---|
| **Dashboard** | http://127.0.0.1:8000 |
| **JSON API** | http://127.0.0.1:8000/api/... |
| **Interactive API docs** | http://127.0.0.1:8000/docs |

Confirm it is all working with `make smoke`.

## Commands

### Local development (virtual environment)

| Command | What it does |
|---|---|
| `make setup` | Create `.venv` and install the pinned dependencies |
| `make seed` | Build `app/gbd.db` from the seed CSVs (skipped if up to date) |
| `make reseed` | Rebuild the database from scratch |
| `make run` | Start the app (dashboard + API) in the background |
| `make stop` | Stop it again |
| `make restart` | Stop, then start |
| `make status` | Show what is listening on `:8000` |
| `make smoke` | Check that every API endpoint answers |
| `make logs` | Follow the app log |
| `make open` | Open the dashboard in a browser |

### Docker

| Command | What it does |
|---|---|
| `make up` | Build and start the container |
| `make down` | Stop and remove it (frees the port) |
| `make docker-restart` | Rebuild and restart |
| `make docker-logs` | Follow the container logs |
| `make docker-ps` | Show container status |

### Data and housekeeping

| Command | What it does |
|---|---|
| `make refresh` | Ingest the newest GBD export from `data/incoming/` |
| `make clean` | Remove the database, logs, and caches (keeps `.venv`) |
| `make distclean` | Also remove `.venv` |

> **Port in use?** `make stop` shuts down the local process; `make down`
> shuts down the container. Use `make status` to see which of the two is
> holding port 8000 — killing a PID from `lsof` while Docker is running
> fights the Docker proxy rather than stopping the container.

## The dashboard

A single self-contained page, `static/index.html`, with no build step
and no external requests — Chart.js is vendored into `static/assets/`, so the
dashboard works on an air-gapped or restricted network.

- **UCC identity** — logo top left; principal investigator top right, with
  photograph and a link through to the
  [UCC research profile](https://research.ucc.ie/en/persons/zubair-kabir/).
- **Hero figure and stat tiles** — life expectancy leads; healthy life
  expectancy, tobacco, BMI, and air pollution follow with sparklines and
  change-since-baseline, all computed from live API responses.
- **Republic of Ireland outline** — Natural Earth 10m boundary, projected and
  simplified to a 138-point inline SVG (no image request), used as a masthead
  watermark and a location chip.
- **Light and dark themes** — follows the OS by default, with a toggle that
  persists the choice.
- **Table view on every chart** — each chart has a toggle to the same data as
  an accessible table, so no value is reachable only by hovering.

**On the chart colours.** The series palette is not hand-picked. It uses
validated categorical slots checked in both themes for lightness band, chroma
floor, colour-vision-deficiency separation (protanopia/deuteranopia, Machado
2009 at full severity), a normal-vision separation floor, and contrast against
the surface. Two light-mode hues sit below the 3:1 contrast line, which is only
permitted alongside a relief channel — hence the visible value labels and the
table views. UCC navy and gold are chrome only; they never encode data.

If you change a series colour, re-validate it rather than eyeballing it — a
palette that merely *looks* distinct routinely collapses under CVD simulation.

## Why a virtual environment

`requirements.txt` pins exact versions (FastAPI 0.115, pandas 2.2) because
those are what this pipeline is tested against. A venv keeps them isolated
from the system Python and from every other project on the machine, so a
reviewer or a new researcher gets exactly the tested environment — and
reproducing a result years from now stays possible.

`make setup` handles it. If you prefer to work in the environment directly:

```bash
source .venv/bin/activate      # Windows: .venv\Scripts\activate
deactivate                     # when you are done
```

`.venv/` is disposable and git-ignored — delete and recreate it any time.
The Docker path needs no venv; a container is already an isolated
environment.

## What is actually "live" here — an honest note

IHME does not offer a free, real-time, arbitrary-query REST API for GBD
estimates. GBD is released in **annual rounds** (GBD 2021, GBD 2023, …),
distributed as **bulk CSV exports** via the
[GBD Results Tool](https://vizhub.healthdata.org/gbd-results/). So "live" in
a responsible, honest sense means:

- The **dashboard-to-API** connection is live: the frontend makes real HTTP
  requests and always reflects whatever is currently in the database.
- The **API-to-GBD** connection is a scheduled ETL job (`refresh.sh`, run via
  `make refresh`), re-run when a new GBD round or extract is downloaded.
  Monthly checks are more than sufficient — there is nothing to gain from
  polling more often than IHME actually publishes.

This is the same architecture recommended in the accompanying technical
specification for the Department of Health prototype, and is standard
practice for any dashboard built on an annually-released data source.

## API reference

| Endpoint | Returns |
|---|---|
| `GET /api/meta` | GBD round, source, last updated |
| `GET /api/indicators` | Available trend indicators |
| `GET /api/trend?indicator=tobacco_sev` | Time series for one indicator |
| `GET /api/ranked?type=causes\|risks` | Ranked bar-chart data |
| `GET /api/export.csv?indicator=le` | CSV download, for citation and reuse |
| `GET /api/health` | Liveness check |

```bash
curl http://127.0.0.1:8000/api/meta
curl "http://127.0.0.1:8000/api/trend?indicator=tobacco_sev"
```

## Project layout

```
ucc_gbd_pipeline/
├── Makefile                     All commands (run `make` to list them)
├── app/
│   ├── main.py                  FastAPI app: serves the API and the dashboard
│   └── gbd.db                   SQLite database (created by the ETL)
├── etl/
│   └── load_seed.py             ETL: seed loader + GBD Results Tool adapter
├── data/
│   ├── gbd_seed.csv             Prototype seed data (trend indicators)
│   ├── gbd_ranked_seed.csv      Prototype seed data (top causes/risks)
│   └── incoming/                Drop new GBD Results Tool exports here
├── logo/
│   └── image.png                UCC identity mark (source file)
├── profile_pic/
│   └── zubair_kabir_profile_pic.png   PI photograph (source file)
├── static/
│   ├── index.html               Dashboard, served at /
│   └── assets/
│       ├── ucc-logo.png         Cropped, web-sized logo
│       ├── zubair-kabir.png     PI photograph
│       └── chart.umd.js         Chart.js, vendored (no CDN dependency)
├── requirements.txt             Pinned dependencies
├── refresh.sh                   Scheduled re-ingestion script
├── Dockerfile
└── docker-compose.yml
```

## Connecting a real GBD extract

1. Register for and download a bulk export from the
   [GBD Results Tool](https://vizhub.healthdata.org/gbd-results/) for the
   indicators, locations, and years you need (Ireland, 1990–2023, the
   risk/cause set used in this prototype, or your own selection).
2. Save it into `data/incoming/`.
3. Run `make refresh`.

The adapter in `etl/load_seed.py::ingest_gbd_export()` maps the standard GBD
Results Tool export columns (`cause_name`/`rei_name`, `location_name`,
`sex_name`, `year`, `val`, `metric_name`) into the same schema the seed data
uses, so the API and dashboard need no changes when you switch from seed data
to a real extract. Pass an `indicator_map` dict to keep stable, short IDs
across re-ingests (recommended) rather than relying on the auto-slugified
names.

To run the refresh on a schedule, add a monthly cron entry:

```cron
0 3 1 * *  cd /path/to/ucc_gbd_pipeline && make refresh >> /var/log/gbd_refresh.log 2>&1
```

## Deployment

`make up` runs the whole stack from `docker-compose.yml` and works as-is on:

- A UCC IT-provisioned Linux VM — the most straightforward route. Ask UCC IT
  Services for a small VM with Docker; this is a common, low-overhead request
  for a research group.
- UCC's research computing environment, if it supports containerised services.
- A free-tier or low-cost external host (Fly.io, Render) for a public-facing
  research demo, if data governance permits — see below.

## Data governance note for UCC

IHME's GBD data is free to use with attribution under IHME's
[Free-to-Use Data Terms](https://www.healthdata.org/gbd/about/data-terms).
Before any public-facing deployment, as opposed to internal research use,
confirm:

- The specific citation IHME requires is included (see `/api/meta`, and add a
  citation footer to any public dashboard).
- Whether your use case counts as "redistribution" under IHME's terms.
  Serving pre-aggregated indicators via this API is generally consistent with
  permitted use, but check the current terms before wider release — they are
  IHME's to set and can change.
- UCC's own research data management policy for externally-hosted services,
  if not hosting internally.
- UCC brand guidelines for use of the university identity mark on anything
  public-facing.

## Extending this prototype

- **Add locations** — the schema already supports a `location` column. Extend
  the ETL and seed data to cover more countries; see the GCC and
  international-benchmarking work already done in this evidence series for a
  working example of multi-location GBD queries.
- **Add authentication** — if this needs restricted researcher-only views,
  add an API key or UCC SSO check in `app/main.py` before deploying beyond a
  local network.
- **Swap SQLite for Postgres** — SQLite is fine for a research prototype at
  this scale. If usage grows, swap the `sqlite3` calls in `app/main.py` for
  SQLAlchemy against Postgres; the schema translates directly.

---

<div align="center">

Not for clinical or diagnostic use.

</div>
