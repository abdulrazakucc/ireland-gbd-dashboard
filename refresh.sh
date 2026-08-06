#!/usr/bin/env bash
# refresh.sh -- re-run the ETL pipeline against the latest data extract.
#
# GBD is released on an ANNUAL cycle (a new "round" each year, e.g. GBD 2021,
# GBD 2023). There is no benefit to running this more than once per round is
# published -- do not schedule this hourly/daily; monthly-or-less is plenty,
# just to check whether IHME has published anything new.
#
# Typical use:
#   1. A researcher downloads a fresh export from the GBD Results Tool
#      (https://vizhub.healthdata.org/gbd-results/) as
#      data/incoming/IHME-GBD_<round>_DATA.csv
#   2. This script ingests it and restarts the API so it picks up the
#      refreshed database.
#
# Schedule with cron (edit crontab -e), e.g. monthly on the 1st at 03:00:
#   0 3 1 * *  /path/to/ucc_pipeline/refresh.sh >> /var/log/gbd_refresh.log 2>&1
#
# Or with a GitHub Actions workflow (.github/workflows/refresh.yml):
#   on:
#     schedule:
#       - cron: '0 3 1 * *'
#   jobs:
#     refresh:
#       runs-on: ubuntu-latest
#       steps:
#         - uses: actions/checkout@v4
#         - run: pip install -r requirements.txt
#         - run: python etl/load_seed.py --gbd-export data/incoming/latest.csv
#         - run: git add app/gbd.db && git commit -m "Scheduled GBD refresh" && git push

set -euo pipefail
cd "$(dirname "$0")"

INCOMING="data/incoming"
LATEST=$(ls -t "$INCOMING"/*.csv 2>/dev/null | head -n1 || true)

if [ -z "$LATEST" ]; then
  echo "No new export found in $INCOMING/. Nothing to do."
  exit 0
fi

# Prefer the project virtual environment. cron runs with a bare environment,
# so a plain `python3` here would use the system interpreter, which does not
# have pandas installed.
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
  echo "Warning: .venv not found, falling back to system python3." >&2
fi

echo "Ingesting $LATEST ..."
"$PYTHON" etl/load_seed.py --gbd-export "$LATEST"

if docker compose version >/dev/null 2>&1; then
  echo "Restarting the app container..."
  docker compose restart app
elif command -v docker-compose >/dev/null 2>&1; then
  echo "Restarting the app container..."
  docker-compose restart app
else
  echo "Restart the app (make restart) to pick up the refreshed database."
fi

echo "Done."
