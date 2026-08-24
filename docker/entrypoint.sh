#!/bin/sh
# Container entrypoint.
#
# The database lives in the mounted data volume so the host and the container
# share one file. That means the image cannot rely on a database baked in at
# build time -- the mount would hide it. So: seed on first start if the file
# is not there, then hand over to the real command (uvicorn).
set -e

DB="${GBD_DB_PATH:-/srv/data/gbd.db}"

DB_DIR="$(dirname "$DB")"

# The data directory is a bind mount, so its ownership comes from the host and
# the image cannot chown it. If the container's user cannot write there, say so
# in one line rather than failing later inside the ETL with a bare traceback.
if [ ! -w "$DB_DIR" ]; then
  echo "!! $DB_DIR is not writable by this container (running as UID $(id -u))." >&2
  echo "!! Start it with 'make up', which runs the container as your own user." >&2
  exit 1
fi

if [ ! -f "$DB" ]; then
  echo "==> No database at $DB -- seeding from the bundled CSVs"
  python -m etl.load_seed
else
  echo "==> Using existing database at $DB"
fi

exec "$@"
