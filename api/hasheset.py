"""Confirmed NIST RDS V3 on-disk layout, the fixture builder, and the Hash Set.

The reference data set V3 is a plain SQLite database. The Minimal set (the one
nsrllookup serves) is a ``.db`` whose single per-file table, ``METADATA``,
carries every supported digest for a file in one row. Digests are stored
UPPERCASE and the table has no standalone hash index, so a raw
``WHERE <algo> = ?`` predicate is a full scan -- which is why nsrllookup
builds a per-algorithm hash->known index at ingest instead of querying the
column directly (see ``docs/adr/0001-disk-based-v3-engine.md``).

This module owns the schema constants, a fixture builder that produces a tiny,
in-repo SQLite database with the same layout as the real Minimal set, and the
provisioned, queryable **Hash Set**: a per-algorithm index plus the
**Provenance** (the **Set**, the **Release** date-version, and the applied
**Delta releases**) that says exactly what is loaded.
"""

import os
import sqlite3
from typing import Any
from typing import Dict
from typing import Sequence
from typing import Set

TABLE = "METADATA"

# Columns in the real RDS V3 METADATA table. Order mirrors NIST's layout.
COLUMNS = ("crc32", "md5", "md5sha1", "sha1", "sha256", "filename")

# Digest columns that are not standalone lookup algorithms.
CRC32_COLUMN = "crc32"

# The digest algorithms nsrllookup accepts, and the column that holds each.
# CRC-32 is physically present in every row but is NOT a supported lookup
# algorithm (see docs/adr/0001-disk-based-v3-engine.md).
ALGORITHM_COLUMN = {
    "md5": "md5",
    "sha1": "sha1",
    "sha256": "sha256",
}

SUPPORTED_ALGORITHMS: Set[str] = set(ALGORITHM_COLUMN)


def build_minimal_fixture_db(path: str, rows: Sequence[dict]) -> None:
    """Create a minimal-style RDS V3 SQLite database at ``path``.

    ``rows`` is a sequence of dicts keyed by the :data:`COLUMNS` names; values
    are the exact strings NIST would store (digests UPPERCASE). Any column
    omitted from a row is written NULL, mirroring how a real row may lack a
    digest it never computed. The table is created with no user-defined index
    on the digest columns, reproducing the "no standalone hash index" property
    of the real set.
    """
    if os.path.exists(path):
        os.remove(path)

    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE {} ("
            "crc32 TEXT, "
            "md5 TEXT, "
            "md5sha1 TEXT, "
            "sha1 TEXT, "
            "sha256 TEXT, "
            "filename TEXT"
            ");".format(TABLE)
        )
        placeholders = ", ".join(["?"] * len(COLUMNS))
        column_list = ", ".join(COLUMNS)
        for row in rows:
            values = [row.get(column) for column in COLUMNS]
            conn.execute(
                "INSERT INTO {} ({}) VALUES ({})".format(
                    TABLE, column_list, placeholders
                ),
                tuple(values),
            )
        conn.commit()
    finally:
        conn.close()


def known_digests(conn: sqlite3.Connection, algorithm: str) -> Set[str]:
    """Return the set of digests present in an algorithm's column.

    This is the raw full-scan view (no index); the lookup layer builds a
    per-algorithm index from it instead of issuing this per request.
    """
    column = ALGORITHM_COLUMN[algorithm]
    cursor = conn.execute("SELECT {} FROM {}".format(column, TABLE))
    return {row[0] for row in cursor if row[0]}


class Provenance:
    """The identity of a loaded Hash Set: which **Set**, **Release** date-version,
    and **Delta releases** it was built from. Surfaced in every Lookup Result and
    on ``/health`` so an answer is only trustworthy through what it records.
    """

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
    """A provisioned, queryable **Hash Set**: one full Release plus applied
    **Delta releases**, with a per-algorithm **hash->known index** built at
    ingest. V3 stores digests UPPERCASE with no standalone hash index, so the
    per-request lookup is a dict membership test, not a full table scan
    (see ``docs/adr/0001-disk-based-v3-engine.md``).
    """

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
        """Membership at the data layer: is this UPPERCASE digest present for
        ``algorithm``. Distinguishes **Known** from **Unknown**; well-formedness
        (the **Invalid** status) is the lookup module's call, not the data
        layer's.
        """
        return digest in self._index[algorithm]


def provision(path: str, provenance: Provenance) -> HashSet:
    """Ingest entry point: build the per-algorithm index over the Minimal
    **Set** ``db`` at ``path`` and return a queryable **Hash Set** stamped with
    its **Provenance**. The index is built here, once, not per request.
    """
    return HashSet(path, provenance)
