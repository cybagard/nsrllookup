"""Confirmed NIST RDS V3 on-disk layout, fixture builder, Hash Set."""

import os
import sqlite3
import tempfile
from typing import Any
from typing import Dict
from typing import List
from typing import Sequence
from typing import Set

TABLE = "METADATA"

COLUMNS = ("crc32", "md5", "md5sha1", "sha1", "sha256", "filename")

CRC32_COLUMN = "crc32"

ALGORITHM_COLUMN = {
    "md5": "md5",
    "sha1": "sha1",
    "sha256": "sha256",
}

SUPPORTED_ALGORITHMS: Set[str] = set(ALGORITHM_COLUMN)


def build_minimal_fixture_db(path: str, rows: Sequence[dict]) -> None:
    """Create a minimal-style RDS V3 SQLite database at path."""
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE {} (crc32 TEXT, md5 TEXT, md5sha1 TEXT, "
            "sha1 TEXT, sha256 TEXT, filename TEXT)".format(TABLE))
        placeholders = ", ".join(["?"] * len(COLUMNS))
        column_list = ", ".join(COLUMNS)
        for row in rows:
            values = [row.get(column) for column in COLUMNS]
            conn.execute("INSERT INTO {} ({}) VALUES ({})".format(
                TABLE, column_list, placeholders), tuple(values))
        conn.commit()
    finally:
        conn.close()


def known_digests(conn: sqlite3.Connection, algorithm: str) -> Set[str]:
    """Return the digests in an algorithm column (raw full scan, no index)."""
    column = ALGORITHM_COLUMN[algorithm]
    cursor = conn.execute("SELECT {} FROM {}".format(column, TABLE))
    return {row[0] for row in cursor if row[0]}


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
    """Provisioned, queryable Hash Set with a per-algorithm known index."""

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
        """Membership at the data layer; Invalid is the lookup module task."""
        return digest in self._index[algorithm]


def provision(path: str, provenance: Provenance) -> HashSet:
    """Build the per-algorithm index at ingest; return a queryable Set."""
    return HashSet(path, provenance)


def apply_delta(base: HashSet, delta_rows: Sequence[dict],
           delta_release: str) -> HashSet:
    """Apply a Delta: merge rows, rebuild index, refresh provenance."""
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
    """Read every row of a Minimal Set db into row dicts for delta merge."""
    conn = sqlite3.connect(path)
    try:
        cursor = conn.execute("SELECT {} FROM {}".format(
            ", ".join(COLUMNS), TABLE))
        return [dict(zip(COLUMNS, row)) for row in cursor]
    finally:
        conn.close()
