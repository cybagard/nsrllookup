"""NIST RDS V3 real Minimal layout, fixture builder, and queryable Hash Set.

The data layer is re-based onto NIST's real Minimal Set, byte-confirmed in
ticket 01 from the shipped `schema.sql`: a `FILE` table
(`sha256, sha1, md5, crc32, file_name, file_size, package_id`) and a
`DISTINCT_HASH` (`sha256, sha1, md5, crc32`) view NIST ships. Digests are
stored UPPERCASE. Membership is served by the per-Algorithm Sidecar index,
materialised from `DISTINCT_HASH` and UPPERCASED so it is case-agnostic, rather
than a raw `FILE` scan. `crc32` is a physical column but is not a supported
lookup Algorithm (per CONTEXT.md). The synthetic `METADATA`/`md5sha1`/`filename`
shape is gone.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from typing import Any
from typing import Dict
from typing import Sequence
from typing import Set

TABLE = "FILE"

DISTINCT_HASH_VIEW = "DISTINCT_HASH"

COLUMNS = ("sha256", "sha1", "md5", "crc32",
           "file_name", "file_size", "package_id")

COLUMN_TYPES = {
     "sha256": "VARCHAR",
     "sha1": "VARCHAR",
     "md5": "VARCHAR",
     "crc32": "VARCHAR",
     "file_name": "VARCHAR",
     "file_size": "INTEGER",
     "package_id": "INTEGER",
}

CRC32_COLUMN = "crc32"

ALGORITHM_COLUMN = {
     "md5": "md5",
     "sha1": "sha1",
     "sha256": "sha256",
}

SUPPORTED_ALGORITHMS: Set[str] = set(ALGORITHM_COLUMN)


def build_minimal_fixture_db(path: str, rows: Sequence[dict]) -> None:
    """Create a real-layout Minimal RDS V3 database at `path`.

    The db carries the real `FILE` table and the `DISTINCT_HASH` view NIST
    ships; digests are stored UPPERCASE. Row dicts supply the seven `FILE`
    columns and need not all be present.
    """
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        columns = ", ".join(
              f"   {name} {COLUMN_TYPES[name]}"
              for name in COLUMNS)
        conn.execute(f"CREATE TABLE {TABLE} (\n{columns}\n)")
        column_list = ", ".join(COLUMNS)
        placeholders = ", ".join(["?"] * len(COLUMNS))
        for row in rows:
            values = [row.get(column, None) for column in COLUMNS]
            conn.execute(
                f"INSERT INTO {TABLE} ({column_list}) VALUES ({placeholders})",
                tuple(values))
        conn.execute(
             f"CREATE VIEW {DISTINCT_HASH_VIEW} AS\n"
             "  SELECT DISTINCT sha256, sha1, md5, crc32\n"
             f"  FROM {TABLE};\n")
        conn.commit()
    finally:
        conn.close()


def known_digests(conn: sqlite3.Connection,
                  algorithm: str) -> Set[str]:
    """Return the distinct digests for an Algorithm, UPPERCASED.

    Materialises the `DISTINCT_HASH` view (the ~distinct-digest count) rather
    than scanning the raw `FILE` rows, so membership is a distinct-digest set,
    not a per-file one.
    """
    column = ALGORITHM_COLUMN[algorithm]
    cursor = conn.execute(
         f"SELECT {column} FROM {DISTINCT_HASH_VIEW}")
    return {row[0].upper() for row in cursor if row[0]}


class Provenance:
    """Identity of a loaded Hash Set: Set, Release, applied Deltas."""

    def __init__(self, set_name: str, release: str,
                 deltas: Sequence[str] = ()) -> None:
        self.set_name = set_name
        self.release = release
        self.deltas = tuple(deltas)

    def dataset(self) -> Dict[str, Any]:
        return {
             "set": self.set_name,
             "release": self.release,
             "deltas": list(self.deltas),
         }


class HashSet:
    """Provisioned, queryable Hash Set with a per-algorithm Sidecar index."""

    def __init__(self, path: str, provenance: Provenance) -> None:
        self._path = path
        self._provenance = provenance
        self._index = {
             algorithm: self._build_index(algorithm, path)
             for algorithm in SUPPORTED_ALGORITHMS
         }

    @staticmethod
    def _build_index(algorithm: str, path: str) -> Set[str]:
        conn = sqlite3.connect(path)
        try:
            return known_digests(conn, algorithm)
        finally:
            conn.close()

    @property
    def provenance(self) -> Provenance:
        return self._provenance

    @property
    def path(self) -> str:
        return self._path

    def is_known(self, algorithm: str, digest: str) -> bool:
        """Membership at the data layer; Invalid is the lookup task.

        The input digest is UPPERCASED before lookup, matching the UPPERCASED
        index, so any case resolves.
        """
        return digest.upper() in self._index[algorithm]


def provision(path: str, provenance: Provenance) -> HashSet:
    """Build the per-algorithm Sidecar index at ingest; return a Set."""
    return HashSet(path, provenance)


def apply_delta(base: HashSet, delta_sql: str,
                delta_release: str,
                set_name: str | None = None) -> HashSet:
    """Apply a NIST Delta as an ordered `.sql`, rebuild, refresh provenance.

    NIST ships a Delta release as a SQLite script -- `BEGIN TRANSACTION;
    INSERT/UPDATE/DELETE INTO FILE ...` -- applied to the base Hash Set by
    copy-on-apply and `executescript` (the documented `.read` mechanism, no
    external CLI). It then rebuilds the Sidecar index and records the Release
    plus the now-applied Delta. A Delta is guarded against a base of a
    different Set: a `set_name` is refused when it differs from the base
    (Minimal deltas apply only to Minimal bases, no cross-set application).
    """
    if set_name is not None and set_name != base.provenance.set_name:
        raise ValueError(
              f"delta targets {set_name} but the base is "
              f"{base.provenance.set_name}")
    fd, new_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copyfile(base.path, new_path)
    conn = sqlite3.connect(new_path)
    try:
        conn.executescript(delta_sql)
        conn.commit()
    finally:
        conn.close()
    updated = list(base.provenance.deltas)
    if delta_release not in updated:
        updated.append(delta_release)
    provenance = Provenance(base.provenance.set_name,
                            base.provenance.release, updated)
    return HashSet(new_path, provenance)


def _sql_literal(value: Any) -> str:
    """Render a Python value as a SQL literal for an `executescript` script."""
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def build_delta_sql(rows: Sequence[dict]) -> str:
    """Render a Delta as NIST's ordered `.sql` of `FILE` inserts.

    Each insert carries the real Minimal columns with the value case as given;
    a fixture Delta is a set of inserts against a sample base. A `;` per
    statement plus `BEGIN`/`COMMIT` keep the script `executescript`-safe.
    """
    column_list = ", ".join(COLUMNS)
    statements = ["BEGIN TRANSACTION"]
    for row in rows:
        values = ", ".join(
              _sql_literal(row.get(column)) for column in COLUMNS)
        statements.append(
             f"INSERT INTO {TABLE} ({column_list}) VALUES ({values})")
    statements.append("COMMIT")
    return ";\n".join(statements) + ";\n"
