"""Smoke check: a real-layout Minimal DB builds a queryable Hash Set.

Re-pointed at NIST's real Minimal layout (confirmed in ticket 01 from the
shipped schema.sql): a `FILE` table, a `DISTINCT_HASH` view, digests stored
UPPERCASE, and -- in the raw NIST layout -- no standalone index on the digest
columns. Membership is served by nsrllookup's own per-Algorithm **hash index**
(`idx_md5`, `idx_sha1`, `idx_sha256`), a B-tree `CREATE INDEX` built *inside*
the provisioned database, so a lookup is an indexed on-disk seek rather than a
raw `FILE` scan and costs O(1) memory. The raw layout ships no such index
(it is built at provision); a lookup UPPERCASEs the input to match the
UPPERCASED columns, so it is case-agnostic. `crc32` is present but not a
supported lookup Algorithm. This is an I/O-bound provision/index check that
builds a real SQLite database and queries it -- it does not assert lookup-layer
SQL internals.
"""

import os
import sqlite3
import tempfile

import pytest

from hasheset import ALGORITHM_COLUMN
from hasheset import COLUMNS
from hasheset import SUPPORTED_ALGORITHMS
from hasheset import TABLE
from hasheset import provision
from hasheset import Provenance

SAMPLE_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
SAMPLE_SHA1 = "3FA828B1A5F1D59CCE6D8A9BB2814F025F84B761"
SAMPLE_SHA256 = ("A3F9BCA52E3D62E9E2C9F0E2F3D4C5B6A7E8F90A1B2C3D4E5F60718293A4B5C6D")


def _row(**overrides):
    row = dict(crc32="2E19F1E7",
                md5="11111111111111111111111111111111",
                sha1="3FA828B1A5F1D59CCE6D8A9BB2814F025F84B761",
                sha256=SAMPLE_SHA256,
                file_name="sample.bin", file_size=0, package_id=0)
    row.update(overrides)
    return row


def _build_real_layout(path, rows):
    """Create a real-layout Minimal db: FILE table + DISTINCT_HASH view."""
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE FILE ("
                     "sha256 VARCHAR NOT NULL, sha1 VARCHAR NOT NULL, "
                     "md5 VARCHAR NOT NULL, crc32 VARCHAR NOT NULL, "
                     "file_name VARCHAR NOT NULL, file_size INTEGER NOT NULL, "
                     "package_id INTEGER NOT NULL)")
        for r in rows:
            conn.execute(
                "INSERT INTO FILE "
                "(sha256, sha1, md5, crc32, file_name, file_size, "
                "package_id) VALUES (?,?,?,?,?,?,?)",
                (r["sha256"], r["sha1"], r["md5"], r["crc32"],
                 r["file_name"], r["file_size"], r["package_id"]))
        conn.execute("CREATE VIEW DISTINCT_HASH AS "
                     "SELECT DISTINCT sha256, sha1, md5, crc32 FROM FILE")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def hash_set_path():
    path = os.path.join(tempfile.mkdtemp(), "rds_minimal.db")
    _build_real_layout(path, [
        _row(md5=SAMPLE_MD5, sha1=SAMPLE_SHA1, sha256=SAMPLE_SHA256,
             file_name="known.bin", file_size=11),
        _row(md5="11111111111111111111111111111111",
             file_name="md5-only.bin", file_size=3),
    ])
    return path


def test_file_table_shape_confirms_v3_layout(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        columns = [info[1] for info in
                   conn.execute("PRAGMA table_info({})".format(TABLE))]
        assert columns == list(COLUMNS)
        assert "crc32" in columns
        assert "file_name" in columns
        assert "file_size" in columns
        assert "package_id" in columns
    finally:
        conn.close()


def test_distinct_hash_view_is_defined(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        views = [row[0] for row in
                 conn.execute("SELECT name FROM sqlite_master "
                                "WHERE type='view'")]
        assert "DISTINCT_HASH" in views
    finally:
        conn.close()


def test_digests_stored_uppercase(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        rows = conn.execute("SELECT md5, sha1, sha256 FROM {}".format(TABLE))
        for md5, sha1, sha256 in rows:
            if md5 is not None:
                assert md5 == md5.upper()
            if sha1 is not None:
                assert sha1 == sha1.upper()
            if sha256 is not None:
                assert sha256 == sha256.upper()
    finally:
        conn.close()


def test_raw_layout_ships_no_hash_index(hash_set_path):
     # The raw NIST-style layout carries no index on its digest columns;
     # nsrllookup builds that index *inside* the db at provision, not in the
     # raw archive.
    conn = sqlite3.connect(hash_set_path)
    try:
        indexes = [info[1] for info in
                   conn.execute("PRAGMA index_list({})".format(TABLE))]
        assert indexes == []
    finally:
        conn.close()


def test_provision_builds_in_database_hash_index(hash_set_path):
     # Provision adds the per-Algorithm B-tree index (idx_md5, idx_sha1,
     # idx_sha256) to the same database, so a later lookup is an indexed seek
     # rather than a raw FILE scan.
    provision(hash_set_path, Provenance("modern", "2026.03.1"))
    conn = sqlite3.connect(hash_set_path)
    try:
        indexes = [info[1] for info in
                   conn.execute("PRAGMA index_list({})".format(TABLE))]
    finally:
        conn.close()
    assert "idx_md5" in indexes
    assert "idx_sha1" in indexes
    assert "idx_sha256" in indexes


def test_membership_is_answered_per_algorithm(hash_set_path):
      # Membership resolves per Algorithm on the in-database index: each
      # supported digest is Known under its own algorithm, a bogus digest is
      # Unknown.
    set_obj = provision(hash_set_path, Provenance("modern", "2026.03.1"))
    assert set_obj.is_known("md5", SAMPLE_MD5)
    assert set_obj.is_known("sha1", SAMPLE_SHA1)
    assert set_obj.is_known("sha256", SAMPLE_SHA256)
    assert not set_obj.is_known("md5", "2977520A5C5FAAD2286D58675E400412")


def test_membership_is_case_agnostic(hash_set_path):
    set_obj = provision(hash_set_path, Provenance("modern", "2026.03.1"))
    assert set_obj.is_known("md5", SAMPLE_MD5.lower())
    assert set_obj.is_known("sha256", SAMPLE_SHA256.lower())


def test_crc32_present_but_not_an_algorithm(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        values = [row[0] for row in
                  conn.execute("SELECT crc32 FROM {} WHERE crc32 IS NOT NULL"
                               .format(TABLE))]
        assert values
        assert "crc32" not in ALGORITHM_COLUMN
        assert "crc32" not in SUPPORTED_ALGORITHMS
        assert SUPPORTED_ALGORITHMS == {"md5", "sha1", "sha256"}
    finally:
        conn.close()
