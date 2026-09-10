#!/usr/bin/env bash
#
# refresh.sh -- replace the live database with a new GBD export, safely.
#
#   new GBD file -> validate -> build new database -> verify -> activate
#
# The import builds a complete new database beside the live one and swaps it in
# only after it has been validated and verified. If anything fails -- a missing
# column, an invalid row, a duplicate estimate, a failed check -- this exits
# non-zero and the dashboard keeps serving the database it had.
#
# GBD is published on an ANNUAL cycle (a new round each time, e.g. GBD 2021,
# GBD 2023). Running this more often than IHME publishes gains nothing.
#
# Typical use:
#   1. Download an export from the GBD Results Tool
#      (https://vizhub.healthdata.org/gbd-results/) into data/incoming/.
#   2. Run `make refresh`                      (imports the newest CSV there)
#      or   scripts/refresh.sh part-1.csv part-2.csv   (a download split in parts)
#      Set GBD_ROUND="GBD 2023" if the filename does not name the release.
#
# Schedule it with cron (crontab -e), e.g. monthly on the 1st at 03:00:
#   0 3 1 * *  /path/to/ireland-gbd-dashboard/scripts/refresh.sh >> /var/log/gbd_refresh.log 2>&1

set -euo pipefail

# Repository root, regardless of where this was invoked from.
cd "$(dirname "$0")/.."

if [ "$#" -gt 0 ]; then
  FILES=("$@")
else
  LATEST=$(ls -t data/incoming/*.csv 2>/dev/null | head -n1 || true)
  if [ -z "$LATEST" ]; then
    echo "No new export found in data/incoming/. Nothing to do."
    exit 0
  fi
  FILES=("$LATEST")
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

echo "Importing: ${FILES[*]}"
if ! "$PYTHON" -m etl.load_seed --gbd-export "${FILES[@]}"; then
  echo "Refresh FAILED. The live database was not changed." >&2
  exit 1
fi

# The app opens the database per request, so it serves the new file from the
# next request on. Restarting the container anyway makes the refresh
# unambiguous in the logs.
if docker compose version >/dev/null 2>&1 && docker compose ps --quiet app 2>/dev/null | grep -q .; then
  echo "Restarting the app container..."
  docker compose restart app
fi

echo "Done."
