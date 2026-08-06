"""
UCC School of Public Health -- Ireland GBD Dashboard.

One process serves both the dashboard and the API on a single port:

    uvicorn app.main:app --reload --port 8000
    -> http://127.0.0.1:8000/          the dashboard
    -> http://127.0.0.1:8000/api/...   the JSON API

Endpoints:
    GET /                                   -> the dashboard (static/index.html)
    GET /api/meta                           -> GBD round, source, last updated
    GET /api/indicators                     -> list of available trend indicators
    GET /api/trend?indicator=tobacco_sev    -> time series for one indicator
    GET /api/ranked?type=causes|risks       -> ranked bar-chart data
    GET /api/export.csv?indicator=...       -> CSV download (for citation / reuse)
"""
import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import io
import csv

DB_PATH = Path(__file__).resolve().parent / "gbd.db"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Ireland GBD Dashboard API",
    description="Serves Global Burden of Disease indicators for Ireland, "
                 "maintained by the UCC School of Public Health.",
    version="0.1.0",
)

# Allow the dashboard (served from anywhere, e.g. a static file or another
# origin during development) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def query(sql, params=()):
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database not initialised. Run: python etl/load_seed.py",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/meta")
def meta():
    rows = query("SELECT key, value FROM meta")
    return {r["key"]: r["value"] for r in rows}


@app.get("/api/indicators")
def indicators():
    rows = query(
        "SELECT DISTINCT indicator_id, indicator_label, unit "
        "FROM trend_indicator ORDER BY indicator_label"
    )
    return rows


@app.get("/api/trend")
def trend(
    indicator: str = Query(..., description="indicator_id, see /api/indicators"),
    location: str = Query("Ireland"),
    sex: str = Query("combined"),
):
    rows = query(
        "SELECT year, value, unit, indicator_label FROM trend_indicator "
        "WHERE indicator_id = ? AND location = ? AND sex = ? ORDER BY year",
        (indicator, location, sex),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for indicator '{indicator}'")
    return {
        "indicator": indicator,
        "label": rows[0]["indicator_label"],
        "unit": rows[0]["unit"],
        "location": location,
        "sex": sex,
        "series": [{"year": r["year"], "value": r["value"]} for r in rows],
    }


@app.get("/api/ranked")
def ranked(
    type: str = Query(..., pattern="^(causes|risks)$"),
    location: str = Query("Ireland"),
    year: int = Query(2023),
):
    rows = query(
        "SELECT label, value, unit FROM ranked_indicator "
        "WHERE rank_type = ? AND location = ? AND year = ? ORDER BY value DESC",
        (type, location, year),
    )
    return {"type": type, "location": location, "year": year, "items": rows}


@app.get("/api/export.csv")
def export_csv(indicator: str = Query(...), location: str = Query("Ireland")):
    rows = query(
        "SELECT indicator_id, indicator_label, location, sex, year, value, unit, gbd_round "
        "FROM trend_indicator WHERE indicator_id = ? AND location = ? ORDER BY year",
        (indicator, location),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No data")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={indicator}.csv"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


# The dashboard is served by this same app, so there is one process and one
# port to run, deploy, and firewall -- and the frontend calls the API on its
# own origin, so no CORS round-trip and nothing to reconfigure on deployment.
#
# This mount is declared LAST on purpose: FastAPI matches routes in order, so
# every /api/... route above is resolved before the catch-all reaches "/".
# html=True makes StaticFiles serve index.html for "/".
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="dashboard")
