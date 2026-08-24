#!/usr/bin/env bash
#
# refresh.sh -- re-run the ETL against the newest export in data/incoming/.
#
# GBD is published on an ANNUAL cycle (a new round each time, e.g. GBD 2021,
# GBD 2023). There is nothing to gain from running this more often than IHME
# actually publishes -- monthly, or on notification of a new round, is plenty.
#
# Typical use:
#   1. Download a fresh export from the GBD Results Tool
#      (https://vizhub.healthdata.org/gbd-results/) into data/incoming/.
#   2. Run `make refresh`.
#
# Schedule it with cron (crontab -e), e.g. monthly on the 1st at 03:00:
#   0 3 1 * *  /path/to/ireland-gbd-dashboard/scripts/refresh.sh >> /var/log/gbd_refresh.log 2>&1

set -euo pipefail

# Repository root, regardless of where this was invoked from.
cd "$(dirname "$0")/.."

INCOMING="data/incoming"
LATEST=$(ls -t "$INCOMING"/*.csv 2>/dev/null | head -n1 || true)

if [ -z "$LATEST" ]; then
  echo "No new export found in $INCOMING/. Nothing to do."
  exit 0
fi

# Prefer the project virtual environment. cron runs with a bare environment,
# so a plain `python3` here would be the system interpreter, which does not
# have this project's dependencies installed.
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
  echo "Warning: .venv not found, falling back to system python3." >&2
fi

echo "Ingesting $LATEST ..."
"$PYTHON" -m etl.load_seed --gbd-export "$LATEST"

# The container reads the same database file through its data mount, so it
# picks this up with no restart. Restarting anyway is harmless and makes the
# refresh unambiguous in the logs.
if docker compose version >/dev/null 2>&1 && docker compose ps --quiet app 2>/dev/null | grep -q .; then
  echo "Restarting the app container..."
  docker compose restart app
fi

echo "Done."
