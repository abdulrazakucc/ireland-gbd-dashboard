"""
SQLite access for the read-only API.

The API only ever reads, so this module is deliberately small: open a
connection, run a query, hand back plain dictionaries, close the connection.
Rows come back as ``dict`` rather than ``sqlite3.Row`` so that callers -- and
FastAPI's JSON serialiser -- never need to know sqlite3 was involved.

Why a fresh connection per query: SQLite connections are cheap, and the
default ``check_same_thread`` guard makes a shared connection unsafe across
the thread-pool FastAPI runs sync endpoints on. At this scale (a single-file
database of a few thousand rows) the cost is irrelevant and the simplicity is
worth a great deal. If this ever moves to Postgres, this module is the only
one that changes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from app.config import DB_PATH


class DatabaseNotInitialised(RuntimeError):
    """Raised when the database file does not exist yet.

    This is an operator error, not a client error: the ETL has not been run.
    The API layer turns it into a 503 with instructions rather than a 500.
    """


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection to the database, closing it on the way out."""
    if not DB_PATH.exists():
        raise DatabaseNotInitialised(f"No database at {DB_PATH}. Build it with: make seed")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query(sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Run ``sql`` and return every row as a dictionary.

    Args:
        sql: A SELECT statement, with ``?`` placeholders for any values.
        params: Values bound to those placeholders. Always pass user input
            this way -- never format it into the SQL string.

    Raises:
        DatabaseNotInitialised: If the database file is missing.
    """
    with connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
