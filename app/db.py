"""
SQLite access for the read-only API, and the database format itself.

The API only ever reads, so the access half of this module is deliberately
small: open a connection, run a query, hand back plain dictionaries, close the
connection. The format half -- :data:`SCHEMA` and :data:`SCHEMA_VERSION` --
lives here too, because the importer that *writes* this format and the API
that *reads* it must never disagree about it.

Why a fresh connection per query: SQLite connections are cheap, and the
default ``check_same_thread`` guard makes a shared connection unsafe across the
thread-pool FastAPI runs sync endpoints on. It also means a refresh that
atomically swaps the database file in is picked up by the very next request,
with no restart.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app import config

# Bump whenever SCHEMA changes shape. The API refuses to read a database built
# for a different version rather than failing later with "no such column".
SCHEMA_VERSION = 2

# One row per GBD estimate, with every dimension kept separate.
#
# cause and risk are NOT NULL with '' meaning "this dimension does not apply"
# (life expectancy has neither; a summary exposure value has a risk but no
# cause). They cannot be NULL: SQLite treats NULLs as distinct in a UNIQUE
# constraint, which would let two copies of the same estimate coexist -- the
# exact silent duplication this table exists to prevent.
#
# series_id identifies one line on a chart: every dimension except year. It is
# derived (see etl.gbd_import.series_id) and stored so the dashboard and the
# downloads can address a series with one short, URL-safe token.
SCHEMA = """
CREATE TABLE gbd_estimate (
    release    TEXT    NOT NULL,
    measure    TEXT    NOT NULL,
    metric     TEXT    NOT NULL,
    location   TEXT    NOT NULL,
    sex        TEXT    NOT NULL,
    age        TEXT    NOT NULL,
    cause      TEXT    NOT NULL DEFAULT '',
    risk       TEXT    NOT NULL DEFAULT '',
    year       INTEGER NOT NULL,
    value      REAL    NOT NULL,
    lower      REAL,
    upper      REAL,
    series_id  TEXT    NOT NULL,
    UNIQUE (release, measure, metric, location, sex, age, cause, risk, year),
    CHECK ((lower IS NULL) = (upper IS NULL)),
    CHECK (lower IS NULL OR lower <= upper)
);
CREATE INDEX idx_estimate_series ON gbd_estimate (series_id, year);
CREATE INDEX idx_estimate_ranking ON gbd_estimate (measure, metric, location, sex, age, year);

-- Dataset-level provenance: release, import time, source, row count.
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- One row per file the dataset was built from.
CREATE TABLE source_file (
    filename  TEXT    NOT NULL,
    sha256    TEXT    NOT NULL,
    bytes     INTEGER NOT NULL,
    row_count INTEGER NOT NULL
);
"""


class DatabaseNotInitialised(RuntimeError):
    """Raised when the database is missing or was built for another schema.

    This is an operator error, not a client error: the ETL has not been run, or
    has not been re-run since an upgrade. The API turns it into a 503 with
    instructions rather than a 500.
    """


# (path, mtime, inode, size) of files already checked, so the version check
# costs one stat() per query rather than one extra query. A refresh replaces
# the file, which changes the key, which re-runs the check.
_checked: set[tuple[str, int, int, int]] = set()


def _check_schema(conn: sqlite3.Connection, path: Path) -> None:
    stat = os.stat(path)
    key = (str(path), stat.st_mtime_ns, stat.st_ino, stat.st_size)
    if key in _checked:
        return
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.DatabaseError:
        row = None
    if row is None or row[0] != str(SCHEMA_VERSION):
        raise DatabaseNotInitialised(
            f"The database at {path} was built by an older version of this project. "
            "Rebuild it with: make reseed, or python etl/load_seed.py (seed data); "
            "or re-import your GBD export with: make refresh"
        )
    _checked.add(key)


@contextmanager
def connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a read connection to the database, closing it on the way out."""
    path = Path(db_path or config.DB_PATH)
    if not path.exists():
        raise DatabaseNotInitialised(
            f"No database at {path}. Build it with: make seed (or: python etl/load_seed.py)"
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _check_schema(conn, path)
        yield conn
    finally:
        conn.close()


def query(
    sql: str, params: Sequence[Any] = (), db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Run ``sql`` and return every row as a dictionary.

    Args:
        sql: A SELECT statement, with ``?`` placeholders for any values.
        params: Values bound to those placeholders. Always pass user input
            this way -- never format it into the SQL string.
        db_path: The database to read. Defaults to the configured one.

    Raises:
        DatabaseNotInitialised: If the database is missing or out of date.
    """
    with connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
