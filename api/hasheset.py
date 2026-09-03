"""NIST RDS V3 real Minimal layout, fixture builder, queryable Hash Set.

The data layer is re-based onto NIST's real Minimal Set, byte-confirmed in
ticket 01 from the shipped `schema.sql`: a `FILE` table
(`sha256, sha1, md5, crc32, file_name, file_size, package_id`) and a
`DISTINCT_HASH` (`sha256, sha1, md5, crc32`) **view** NIST ships. Digests are
stored UPPERCASE. Membership is served by the per-Algorithm **Sidecar index**,
materialised from `DISTINCT_HASH` and UPPERCASED so it is case-agnostic, rather
than a raw `FILE` scan. `crc32` is a physical column but is not a supported
lookup Algorithm (per CONTEXT.md). The synthetic `METADATA`/`md5sha1`/`filename`
shape is gone.
"""

import os
import sqlite3
import tempfile
from typing import Any
from typing import Dict
from typing import List
from typing import Sequence
from typing import Set

TABLE = "FILE"

DISTINCT_HASH_VIEW = "DISTINCT_HASH"

COLUMNS = ("sha256", "sha1", "md5", "crc32",
           "file_name", "file_size", "package_id")

CRC32_COLUMN = "crc32"

ALGORITHM_COLUMN = {
       "md5": "md5",
       "sha1": "sha1",
       "sha256": "sha256",
   }

SUPPORTED_ALGORITHMS: Set[str] = set(ALGORITHM_COLUMN)


def build_minimal_fixture_db(path: str, rows: Sequence[dict]) -> None:
    """Create a real-layout Minimal RDS V3 database at path.

    The db carries the real `FILE` table and the `DISTINCT_HASH` view NIST
    ships; digests are stored UPPERCASE. Row dicts supply the seven `FILE`
    columns and need not all be present.
    """
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE {} (\n"
                      "  sha256 VARCHAR,\n"
                      "  sha1 VARCHAR,\n"
                      "  md5 VARCHAR,\n"
                      "  crc32 VARCHAR,\n"
                      "  file_name VARCHAR,\n"
                      "  file_size INTEGER,\n"
                      "  package_id INTEGER\n"
                      ")".format(TABLE))
        column_list = ", ".join(COLUMNS)
        placeholders = ", ".join(["?"] * len(COLUMNS))
        for row in rows:
            values = [row.get(column, None) for column in COLUMNS]
            conn.execute("INSERT INTO {} ({}) VALUES ({})".format(
                TABLE, column_list, placeholders), tuple(values))
        conn.execute("CREATE VIEW {} AS\n"
                     "  SELECT DISTINCT sha256, sha1, md5, crc32\n"
                     "    FROM {};\n".format(DISTINCT_HASH_VIEW, TABLE))
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
        "SELECT {} FROM {}".format(column, DISTINCT_HASH_VIEW))
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

    def is_known(self, algorithm: str, digest: str) -> bool:
        """Membership at the data layer; Invalid is the lookup task.

      The input digest is UPPERCASED before lookup, matching the UPPERCASED
      index, so any case resolves.
      """
        return digest.upper() in self._index[algorithm]


def provision(path: str, provenance: Provenance) -> HashSet:
    """Build the per-algorithm Sidecar index at ingest; return a Set."""
    return HashSet(path, provenance)


def apply_delta(base: "HashSet", delta_rows: Sequence[dict],
                delta_release: str) -> "HashSet":
    """Apply a Delta: merge rows, rebuild the index, refresh provenance.

    Tests model a Delta as a set of inserts; ticket 04 reworks this to NIST's
    ordered `.sql` shape.
    """
    fd, new_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    build_minimal_fixture_db(new_path,
        _copy_rows(base._path) + list(delta_rows))
    updated = list(base.provenance.deltas)
    if delta_release not in updated:
        updated.append(delta_release)
    provenance = Provenance(base.provenance.set_name,
                            base.provenance.release, updated)
    return HashSet(new_path, provenance)


def _copy_rows(path: str) -> List[dict]:
    """Read every `FILE` row of a Minimal Set db into row dicts for merge."""
    conn = sqlite3.connect(path)
    try:
        cursor = conn.execute("SELECT {} FROM {}".format(
            ", ".join(COLUMNS), TABLE))
        return [dict(zip(COLUMNS, row)) for row in cursor]
    finally:
        conn.close()
