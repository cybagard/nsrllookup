"""NIST RDS V3 real Minimal layout, fixture builder, and queryable Hash Set.

The data layer is re-based onto NIST's real Minimal Set, byte-confirmed in
ticket 01 from the shipped `schema.sql`: a `FILE` table
(`sha256, sha1, md5, crc32, file_name, file_size, package_id`) and a
`DISTINCT_HASH` (`sha256, sha1, md5, crc32`) view NIST ships. Digests are
stored UPPERCASE. Membership is served by a per-Algorithm **hash index** -- a
B-tree `CREATE INDEX` on each digest column (`idx_md5`, `idx_sha1`,
`idx_sha256`) built **inside the mounted Hash Set's own `.db`**, so a lookup
is an indexed on-disk seek, not a raw `FILE` scan, and costs O(1) memory rather
than materialising the distinct-digest set in RAM. The index lives in the same
database as the rows it covers (no second dataset, no copy to keep in sync --
ADR-0001), and a lookup UPPERCASEs the input digest to match the UPPERCASED
columns, so membership is case-agnostic. `crc32` is a physical column but is not
a supported lookup Algorithm (per CONTEXT.md). The synthetic
`METADATA`/`md5sha1`/`filename` shape is gone.
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

# The per-Algorithm hash index lives inside the Hash Set's own `.db`: one B-tree
# index per lookup Algorithm column (idx_md5, idx_sha1, idx_sha256), built by
# `build_hash_index` at provision so a membership lookup is an indexed on-disk
# seek, not a raw `FILE` scan. No separate on-disk sidecar -- the index and the
# rows it covers are the one and same database (ADR-0001).
HASH_INDEX_NAMES = ["idx_" + algorithm for algorithm in ALGORITHM_COLUMN]


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
            f"    {name} {COLUMN_TYPES[name]}"
            for name in COLUMNS)
        conn.execute(f"CREATE TABLE {TABLE} (\n{columns}\n)")
        column_list = ", ".join(COLUMNS)
        placeholders = ", ".join(["?"] * len(COLUMNS))
        for row in rows:
            values = [row.get(column, None) for column in COLUMNS]
            conn.execute(
                f"INSERT INTO {TABLE} ({column_list}) VALUES "
                f"({placeholders})",
                tuple(values))
        conn.execute(
            f"CREATE VIEW {DISTINCT_HASH_VIEW} AS\n"
            "  SELECT DISTINCT sha256, sha1, md5, crc32\n"
            f"  FROM {TABLE};\n")
        conn.commit()
    finally:
        conn.close()


def build_hash_index(db_path: str) -> None:
    """Create the per-Algorithm B-tree index inside the Hash Set's own `.db`.

    One `CREATE INDEX IF NOT EXISTS idx_<algo> ON FILE(<algo>)` per lookup
    Algorithm, built on the writable provisioned database so a membership lookup
    is an indexed seek rather than a raw `FILE` scan. `IF NOT EXISTS` makes it
    idempotent -- cheap on a db that already carries the index (the base
    Minimal db NIST ships, or a re-apply) -- so every provision path can call
    it. The index persists as part of the same database, so it needs no
    separate on-disk artifact, no shipping, and no staleness beyond the rows
    it covers (ADR-0001).
    """
    conn = sqlite3.connect(db_path)
    try:
        _rebuild_index(conn)
        conn.commit()
    finally:
        conn.close()


def _rebuild_index(conn: sqlite3.Connection) -> None:
    """Create the per-Algorithm hash index on an open db connection.

    Runs one `CREATE INDEX IF NOT EXISTS idx_<algo> ON FILE(<algo>)` per
    lookup Algorithm. `IF NOT EXISTS` keeps it idempotent, so calling it on a
    freshly-copied base (which already carries the index) is a no-op. Used by
    `build_hash_index` and by `apply_delta`, which rebuilds the index on its
    copy-on-apply so the refreshed set is indexed (ADR-0001).
    """
    for name in HASH_INDEX_NAMES:
        column = name[len("idx_"):]
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE} ({column})")


class Provenance:
    """Identity of a loaded Hash Set: Set, Release, Deltas, dbhash."""

    def __init__(self, set_name: str, release: str,
                 deltas: Sequence[str] = (),
                 dbhash: str | None = None) -> None:
        self.set_name = set_name
        self.release = release
        self.deltas = tuple(deltas)
        self.dbhash = dbhash

    def dataset(self) -> Dict[str, Any]:
        return {
            "set": self.set_name,
            "release": self.release,
            "deltas": list(self.deltas),
            "dbhash": self.dbhash,
        }


class HashSet:
    """Provisioned, queryable Hash Set with a per-Algorithm hash index.

    Opens the provisioned `.db` read-only and answers membership by an indexed
    on-disk seek, holding no in-RAM digest copy -- the index lives in the
    database itself (ADR-0001), so there is no second dataset and no OOM from
    materialising the distinct-digest set. A single read-only connection is
    shared across lookups to keep the open handles bounded.
    """

    def __init__(self, path: str, provenance: Provenance) -> None:
        self._path = os.fspath(path)
        self._provenance = provenance
        self._conn = sqlite3.connect(
            "file:" + self._path + "?mode=ro", uri=True)

    @property
    def provenance(self) -> Provenance:
        return self._provenance

    @property
    def path(self) -> str:
        return self._path

    def is_known(self, algorithm: str, digest: str) -> bool:
        """Membership at the data layer; Invalid is the lookup task.

        An indexed on-disk seek: the input digest is UPPERCASED to match the
        UPPERCASED column, then compared against the per-Algorithm B-tree
        index, so any case resolves. A single-row existence test needs only the
        index, not the raw `FILE` scan, and holds no copies in RAM.
        """
        cursor = self._conn.execute(
            "SELECT 1 FROM " + TABLE + " WHERE "
            + ALGORITHM_COLUMN[algorithm] + " = ? LIMIT 1",
            (digest.upper(),))
        return cursor.fetchone() is not None


def provision(path: str, provenance: Provenance) -> HashSet:
    """Build the per-Algorithm hash index at ingest; return a Set."""
    build_hash_index(path)
    return HashSet(path, provenance)


def _iter_statements(delta_sql):
    """Yield the statements of a Delta `.sql`, streaming a file when given one.

    A Delta may be a SQL string (the fixture path) or an on-disk `.sql`
    (`os` path-like, the turnkey path). A real Delta is millions of one-line
    `INSERT`s, so a path is streamed line-by-line and never read whole into
    memory.
    """
    if isinstance(delta_sql, os.PathLike):
        with open(delta_sql, encoding="utf-8") as handle:
            yield from handle
    elif isinstance(delta_sql, str):
        yield from delta_sql.splitlines()
    else:
        yield from delta_sql


def _apply_sql_stream(conn, delta_sql, batch=100_000):
    """Apply a Delta `.sql` as a streamed, batched sequence of statements.

    Feeding NIST's single `BEGIN TRANSACTION; ... COMMIT;` of millions of
    `INSERT`s to `executescript` exceeds its script-size limit and the memory
    budget; this streams one statement at a time, skips the wrapper's
    `BEGIN`/`COMMIT` markers and manages its own transactions, committing once
    every `batch` statements so neither the full text nor a mega-transaction is
    ever held at once.
    """
    conn.isolation_level = None
    conn.execute("BEGIN")
    count = 0
    for raw in _iter_statements(delta_sql):
        statement = raw.strip()
        if not statement:
            continue
        upper = statement.upper()
        if upper.startswith("BEGIN") or upper.startswith("START") \
                or upper.startswith("COMMIT"):
            continue
        conn.execute(statement if statement.endswith(
            ";") else statement + ";")
        count += 1
        if count % batch == 0:
            conn.execute("COMMIT")
            conn.execute("BEGIN")
    conn.execute("COMMIT")
    return count


def apply_delta(base: HashSet, delta_sql: str | os.PathLike | None,
                delta_release: str,
                set_name: str | None = None) -> HashSet:
    """Apply a NIST Delta as an ordered `.sql`, rebuild, refresh provenance.

    NIST ships a Delta release as a SQLite script -- `BEGIN TRANSACTION;
    INSERT/UPDATE/DELETE INTO FILE ...` -- applied to the base Hash Set by
    copy-on-apply and a streaming `execute` (the documented `.read` mechanism,
    no external CLI). A Delta `.sql` is a path (streamed) or a SQL text; a real
    delta of millions of inserts is applied in bounded batches, not read whole
    (ADR-0003: no multi-megabyte object in RAM at once). It then rebuilds the
    per-Algorithm hash index on the new database and records the Release plus
    the now-applied Delta. A Delta is guarded against a base of a different
    Set: a `set_name` is refused when it differs from the base (Minimal deltas
    apply only to Minimal bases, no cross-set application).
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
        _apply_sql_stream(conn, delta_sql)
        _rebuild_index(conn)
    finally:
        conn.close()
    updated = list(base.provenance.deltas)
    if delta_release not in updated:
        updated.append(delta_release)
    provenance = Provenance(base.provenance.set_name,
                            base.provenance.release, updated,
                            base.provenance.dbhash)
    return HashSet(new_path, provenance)


def verify_readiness(manifest, hash_set: "HashSet") -> bool:
    """The mount is trusted only when its manifest agrees with it.

    The service is ready when a Provisioning manifest is present and its
    recorded identity -- the Set, the Release, the ordered Delta releases, and
    the final dbhash -- matches the loaded Hash Set provenance. A missing
    manifest or any mismatch means the mount is unverified, so the service is
    not-ready and serves nothing (ADR-0005). Per ADR-0006 the service trusts
    the verified mount; it does not recompute dbhash.
    """
    if manifest is None or hash_set is None:
        return False
    record = {
        "set": manifest.get("set"),
        "release": manifest.get("release"),
        "deltas": manifest.get("deltas"),
        "dbhash": manifest.get("dbhash"),
    }
    return record == hash_set.provenance.dataset()


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
