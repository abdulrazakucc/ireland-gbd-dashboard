"""
Import GBD data: new file -> validate -> build new database -> verify -> activate.

The active database is only ever *replaced*, atomically, by a complete database
that has already been built and checked. It is never written to in place. So a
refresh that fails at any stage -- a bad file, a duplicate estimate, a failed
check, a full disk -- leaves the dashboard serving exactly what it served
before, and leaves no half-built file behind.

Input is the long CSV format of the IHME GBD Results Tool
(https://vizhub.healthdata.org/gbd-results/), in either of its download
styles: ``measure_name, location_name, ...`` ("ID and name") or
``measure, location, ...`` ("name only"). One dataset may span several files,
because the Results Tool splits large downloads.
"""

from __future__ import annotations

import csv
import hashlib
import math
import os
import re
import secrets
import shutil
import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app import config
from app.db import SCHEMA, SCHEMA_VERSION

EXPORT_SOURCE = "IHME GBD Results Tool export"

# Canonical dimension -> header names accepted for it. The last alias of risk
# and value are this project's own CSV export headers, so a downloaded CSV can
# be imported again.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "measure": ("measure_name", "measure"),
    "metric": ("metric_name", "metric"),
    "location": ("location_name", "location"),
    "sex": ("sex_name", "sex"),
    "age": ("age_name", "age"),
    "cause": ("cause_name", "cause"),
    "risk": ("rei_name", "rei", "risk"),
    "year": ("year", "year_id"),
    "value": ("val", "value"),
    "lower": ("lower",),
    "upper": ("upper",),
}
REQUIRED = ("measure", "metric", "location", "sex", "age", "year", "value")
TEXT_DIMS = ("measure", "metric", "location", "sex", "age", "cause", "risk")
SERIES_DIMS = ("release", *TEXT_DIMS)
KEY_DIMS = (*SERIES_DIMS, "year")

MAX_REPORTED = 20  # problems listed in an error; the total is always given
BATCH = 5000


class GBDImportError(Exception):
    """The import was refused. The active database was not touched."""

    def __init__(self, summary: str, problems: Sequence[str] = ()) -> None:
        self.summary = summary
        self.problems = list(problems)
        detail = "".join(f"\n  - {p}" for p in self.problems)
        super().__init__(f"{summary}{detail}\nThe active database was left unchanged.")


class ValidationError(GBDImportError):
    """A file is unreadable, has the wrong columns, or contains an invalid row."""


class DuplicateRecordsError(GBDImportError):
    """Two or more rows describe the same estimate and would overwrite each other."""


class VerificationError(GBDImportError):
    """The newly built database failed its checks, so it was not activated."""


@dataclass(frozen=True)
class SourceFile:
    filename: str  # basename only: a full path would leak server layout via /api/meta
    sha256: str
    bytes: int
    row_count: int


@dataclass(frozen=True)
class ImportReport:
    db_path: Path
    release: str
    source: str
    imported_at: str
    row_count: int
    series_count: int
    files: tuple[SourceFile, ...]
    previous: Path | None
    warnings: tuple[str, ...]


def series_id(*dims: str) -> str:
    """A short, stable, URL-safe id for one series (every key dimension but year)."""
    return hashlib.blake2b("\x1f".join(dims).encode("utf-8"), digest_size=8).hexdigest()


# --------------------------------------------------------------- validate ----


def resolve_release(paths: Sequence[Path], release: str | None) -> str:
    """Decide the release label, refusing when the inputs contradict each other.

    IHME exports carry no release column, but their filenames usually do
    (``IHME-GBD_2021_DATA-...csv``). A file named for 2021 imported as
    "GBD 2023" would mislabel every figure, so that combination is an error.
    """
    named = {
        f"GBD {m.group(1)}"
        for p in paths
        if (m := re.search(r"GBD[_ -]?(\d{4})", Path(p).name, re.IGNORECASE))
    }
    if len(named) > 1:
        raise ValidationError(f"The files name different GBD releases: {sorted(named)}.")
    from_name = next(iter(named), None)
    if release:
        years = re.findall(r"\d{4}", release)
        if from_name and years and from_name[-4:] not in years:
            raise ValidationError(
                f"--release {release!r} contradicts the filename, which names {from_name}."
            )
        return release.strip()
    return from_name or config.GBD_ROUND


def _resolve_columns(header: Sequence[str], name: str) -> tuple[dict[str, str], list[str]]:
    present = {h.strip() for h in header}
    columns: dict[str, str] = {}
    problems: list[str] = []
    for dim, aliases in COLUMN_ALIASES.items():
        found = [a for a in aliases if a in present]
        if len(found) > 1:
            problems.append(f"{name}: ambiguous columns for {dim}: {found} -- keep one.")
        elif found:
            columns[dim] = found[0]
    missing = [d for d in REQUIRED if d not in columns]
    if missing:
        wanted = ", ".join("/".join(COLUMN_ALIASES[d]) for d in missing)
        problems.append(f"{name}: missing required column(s): {wanted}.")
    if ("lower" in columns) != ("upper" in columns):
        problems.append(f"{name}: has only one of lower/upper; uncertainty needs both.")
    return columns, problems


def _number(text: str) -> float | None:
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _read_file(
    path: Path, release: str, problems: list[str], warnings: list[str]
) -> tuple[list[tuple], int]:
    """Parse and validate one file. Returns its rows (empty if any problem) and row count."""
    name = path.name
    rows: list[tuple] = []
    count = 0
    outside_ui = 0
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            columns, header_problems = _resolve_columns(reader.fieldnames or [], name)
            if header_problems:
                problems.extend(header_problems)
                return [], 0
            for raw in reader:
                count += 1
                line = reader.line_num
                row = {d: (raw.get(c) or "").strip() for d, c in columns.items()}
                bad = [d for d in REQUIRED if not row.get(d)]
                if bad:
                    problems.append(f"{name} line {line}: empty {', '.join(bad)}.")
                    continue
                year = _number(row["year"])
                value = _number(row["value"])
                if year is None or not year.is_integer() or not 1950 <= year <= 2100:
                    problems.append(
                        f"{name} line {line}: year {row['year']!r} is not a valid year."
                    )
                    continue
                if value is None:
                    problems.append(f"{name} line {line}: value {row['value']!r} is not a number.")
                    continue
                lower_text, upper_text = row.get("lower", ""), row.get("upper", "")
                lower = upper = None
                if lower_text or upper_text:
                    lower, upper = _number(lower_text), _number(upper_text)
                    if lower is None or upper is None:
                        problems.append(
                            f"{name} line {line}: uncertainty interval needs numeric lower "
                            f"and upper (got {lower_text!r}, {upper_text!r})."
                        )
                        continue
                    if lower > upper:
                        problems.append(f"{name} line {line}: lower {lower} exceeds upper {upper}.")
                        continue
                    if not lower <= value <= upper:
                        outside_ui += 1
                if row["metric"].lower() == "percent" and any(
                    v is not None and abs(v) > 1 for v in (value, lower, upper)
                ):
                    problems.append(
                        f"{name} line {line}: Percent value {row['value']} is outside -1..1. "
                        "IHME exports percentages as proportions (0.12 = 12%)."
                    )
                    continue
                dims = (release, *(row.get(d, "") for d in TEXT_DIMS))
                rows.append((*dims, int(year), value, lower, upper, series_id(*dims), name, line))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        problems.append(f"{name}: could not be read as a UTF-8 CSV ({exc}).")
        return [], count
    if count == 0:
        problems.append(f"{name}: contains no data rows.")
    if outside_ui:
        warnings.append(f"{name}: {outside_ui} estimate(s) lie outside their own interval.")
    return rows, count


def _sha256(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


# ------------------------------------------------------------------ build ----


def _check_duplicates(conn: sqlite3.Connection) -> None:
    keys = ", ".join(KEY_DIMS)
    groups = f"SELECT {keys} FROM staging GROUP BY {keys} HAVING COUNT(*) > 1"
    total = conn.execute(f"SELECT COUNT(*) FROM ({groups})").fetchone()[0]
    if not total:
        return
    examples = conn.execute(
        f"SELECT {keys}, COUNT(*), "
        "COUNT(DISTINCT quote(value) || '|' || quote(lower) || '|' || quote(upper)), "
        "group_concat(file || ' line ' || line, ', ') "
        f"FROM staging GROUP BY {keys} HAVING COUNT(*) > 1 LIMIT {MAX_REPORTED}"
    ).fetchall()
    problems = []
    for row in examples:
        dims = " / ".join(str(v) if v != "" else "-" for v in row[: len(KEY_DIMS)])
        count, distinct, where = row[len(KEY_DIMS) :]
        kind = "conflicting values" if distinct > 1 else "identical values"
        problems.append(f"{dims}: {count} rows with {kind} ({where})")
    raise DuplicateRecordsError(
        f"{total} estimate(s) appear more than once. An estimate is identified by "
        f"{', '.join(KEY_DIMS)}; duplicates would overwrite one another, so nothing "
        "was imported.",
        problems,
    )


def _build(
    build_path: Path,
    paths: Sequence[Path],
    release: str,
    source: str,
    imported_at: str,
    warnings: list[str],
) -> tuple[int, int, tuple[SourceFile, ...]]:
    problems: list[str] = []
    conn = sqlite3.connect(build_path)
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "CREATE TEMP TABLE staging (release, measure, metric, location, sex, age, cause, "
            "risk, year, value, lower, upper, series_id, file, line)"
        )
        files = []
        for path in paths:
            if not path.is_file():
                problems.append(f"{path.name}: file not found ({path}).")
                continue
            rows, count = _read_file(path, release, problems, warnings)
            if not problems:
                for start in range(0, len(rows), BATCH):
                    conn.executemany(
                        "INSERT INTO staging VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        rows[start : start + BATCH],
                    )
            files.append(SourceFile(path.name, *_sha256(path), row_count=count))
        if problems:
            shown = problems[:MAX_REPORTED]
            more = len(problems) - len(shown)
            raise ValidationError(
                f"{len(problems)} problem(s) found in the input"
                + (f" (first {len(shown)} shown)" if more else "")
                + ".",
                shown,
            )

        _check_duplicates(conn)

        conn.execute(
            "INSERT INTO gbd_estimate (release, measure, metric, location, sex, age, cause, "
            "risk, year, value, lower, upper, series_id) SELECT release, measure, metric, "
            "location, sex, age, cause, risk, year, value, lower, upper, series_id FROM staging"
        )
        row_count, series_count, year_min, year_max = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT series_id), MIN(year), MAX(year) FROM gbd_estimate"
        ).fetchone()
        meta = {
            "schema_version": str(SCHEMA_VERSION),
            "release": release,
            "source": source,
            "imported_at": imported_at,
            "row_count": str(row_count),
            "series_count": str(series_count),
            "year_min": str(year_min),
            "year_max": str(year_max),
        }
        conn.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
        conn.executemany(
            "INSERT INTO source_file VALUES (?, ?, ?, ?)",
            [(f.filename, f.sha256, f.bytes, f.row_count) for f in files],
        )
        conn.execute("DROP TABLE staging")
        conn.commit()
        conn.execute("ANALYZE")
        return row_count, series_count, tuple(files)
    finally:
        conn.close()


# ----------------------------------------------------------------- verify ----


def verify_database(path: Path, expected_rows: int, files: Sequence[SourceFile]) -> None:
    """Check a freshly built database before it is allowed to go live."""
    from app import queries

    problems: list[str] = []
    conn = sqlite3.connect(path)
    try:
        if (result := conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            problems.append(f"integrity check failed: {result}")
        meta = dict(conn.execute("SELECT key, value FROM meta"))
        if meta.get("schema_version") != str(SCHEMA_VERSION):
            problems.append("schema version missing or wrong")
        actual = conn.execute("SELECT COUNT(*) FROM gbd_estimate").fetchone()[0]
        if actual != expected_rows or meta.get("row_count") != str(expected_rows):
            problems.append(f"expected {expected_rows} rows, found {actual}")
        file_rows = conn.execute("SELECT COUNT(*), SUM(row_count) FROM source_file").fetchone()
        if file_rows != (len(files), expected_rows):
            problems.append(f"source file provenance does not account for every row: {file_rows}")
    finally:
        conn.close()

    # Read it back through the same queries the API uses: a database the API
    # cannot serve must not go live.
    if not problems:
        catalogue = queries.list_series(path)
        if len(catalogue) != int(meta["series_count"]):
            problems.append("series catalogue does not match the series count")
        elif not queries.fetch_series(path, catalogue[0]["series_id"]):
            problems.append("the first series could not be read back")
    if problems:
        raise VerificationError("The new database failed verification.", problems)


# --------------------------------------------------------------- activate ----


def _activate(build_path: Path, db_path: Path, keep_previous: bool) -> Path | None:
    previous = None
    if keep_previous and db_path.exists():
        previous = db_path.with_name(db_path.name + ".previous")
        shutil.copy2(db_path, previous)
    for attempt in range(5):
        try:
            os.replace(build_path, db_path)  # atomic on the same filesystem
            return previous
        except PermissionError:  # Windows refuses while a reader holds the file open
            if attempt == 4:
                raise
            time.sleep(0.2)
    return previous


def import_dataset(
    paths: Sequence[str | Path],
    *,
    release: str | None = None,
    source: str = EXPORT_SOURCE,
    db_path: Path | None = None,
    keep_previous: bool = True,
) -> ImportReport:
    """Build a database from ``paths`` and make it the active one -- or change nothing.

    Raises:
        ValidationError, DuplicateRecordsError, VerificationError: the import
            was refused; the active database is untouched.
    """
    files_in = [Path(p) for p in paths]
    if not files_in:
        raise ValidationError("No input files were given.")
    db_path = Path(db_path or config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    release = resolve_release(files_in, release)
    imported_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    warnings: list[str] = []

    # Built beside the live file so the final rename stays on one filesystem.
    build_path = db_path.with_name(f".{db_path.name}.building-{os.getpid()}-{secrets.token_hex(4)}")
    try:
        rows, series, files = _build(build_path, files_in, release, source, imported_at, warnings)
        verify_database(build_path, rows, files)
        previous = _activate(build_path, db_path, keep_previous)
    finally:
        for leftover in (build_path, build_path.with_name(build_path.name + "-journal")):
            leftover.unlink(missing_ok=True)

    return ImportReport(
        db_path, release, source, imported_at, rows, series, files, previous, tuple(warnings)
    )
