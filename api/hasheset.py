"""Confirmed NIST RDS V3 on-disk layout and a minimal-set fixture builder.

The reference data set V3 is a plain SQLite database. The Minimal set (the one
nsrllookup serves) is a ``.db`` whose single per-file table, ``METADATA``,
carries every supported digest for a file in one row. Digests are stored
UPPERCASE and the table has no standalone hash index, so a raw
``WHERE <algo> = ?`` predicate is a full scan -- which is why nsrllookup
builds a per-algorithm hash->known index at ingest instead of querying the
column directly (see ``docs/adr/0001-disk-based-v3-engine.md``).

This module owns the schema constants and a fixture builder that produces a
tiny, in-repo SQLite database with the same layout as the real Minimal set,
so the lookup code path exercises identical column names and casing against a
sample rather than an 18 GB download.
"""

import os
import sqlite3
from typing import List
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
