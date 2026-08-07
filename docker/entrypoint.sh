#!/bin/sh
# Container entrypoint.
#
# The database lives in the mounted data volume so the host and the container
# share one file. That means the image cannot rely on a database baked in at
# build time -- the mount would hide it. So: seed on first start if the file
# is not there, then hand over to the real command (uvicorn).
set -e

DB="${GBD_DB_PATH:-/srv/data/gbd.db}"

if [ ! -f "$DB" ]; then
  echo "==> No database at $DB -- seeding from the bundled CSVs"
  python -m etl.load_seed
else
  echo "==> Using existing database at $DB"
fi

exec "$@"
