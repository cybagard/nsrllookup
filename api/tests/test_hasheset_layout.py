"""Smoke check: a small minimal-style DB builds a queryable Hash Set.

This is the I/O-bound provision/index side confirmed by building a real
SQLite database (not by asserting SQL internals of the lookup layer). It
proves the confirmed V3 layout -- a METADATA table with UPPERCASE digests
and no standalone hash index -- is both queryable and distinguishable at
the data layer for known / unknown / invalid, and that CRC-32 is physically
present but not a supported algorithm.
"""

import os
import sqlite3
import tempfile

import pytest

from hasheset import ALGORITHM_COLUMN
from hasheset import COLUMNS
from hasheset import SUPPORTED_ALGORITHMS
from hasheset import TABLE
from hasheset import build_minimal_fixture_db

SAMPLE_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
SAMPLE_SHA1 = "3FA828B1A5F1D59CCE6D8A9BB2814F025F84B761"
SAMPLE_SHA256 = ("A3F9BCA52E3D62E9E2C9F0E2F3D4C5B6A7E8F90A1B2C3D4E5F60718293A4B5C6D")


def _row(**overrides):
    row = dict(crc32="2E19F1E7", md5=None, md5sha1=None,
               sha1=None, sha256=None, filename="sample.bin")
    row.update(overrides)
    return row


@pytest.fixture
def hash_set_path():
    path = os.path.join(tempfile.mkdtemp(), "rds_minimal.db")
    build_minimal_fixture_db(path, [
        _row(md5=SAMPLE_MD5, sha1=SAMPLE_SHA1, sha256=SAMPLE_SHA256,
             filename="known.bin"),
        _row(md5="11111111111111111111111111111111",
             filename="md5-only.bin"),
    ])
    return path


def test_metadata_table_shape_confirms_v3_layout(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        columns = [info[1] for info in
                   conn.execute("PRAGMA table_info({})".format(TABLE))]
        assert columns == list(COLUMNS)
        assert "crc32" in columns
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


def test_no_standalone_hash_index(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        indexes = [info[1] for info in
                   conn.execute("PRAGMA index_list({})".format(TABLE))]
        assert indexes == []
    finally:
        conn.close()


def test_known_unknown_invalid_distinct(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        known = {row[0] for row in
                 conn.execute("SELECT md5 FROM {} WHERE md5 IS NOT NULL"
                              .format(TABLE))}
        assert SAMPLE_MD5 in known
        assert "2977520A5C5FAAD2286D58675E400412" not in known
        assert SUPPORTED_ALGORITHMS == {"md5", "sha1", "sha256"}
        assert "crc32" not in SUPPORTED_ALGORITHMS
    finally:
        conn.close()


def test_crc32_present_but_not_an_algorithm(hash_set_path):
    conn = sqlite3.connect(hash_set_path)
    try:
        values = [row[0] for row in
                  conn.execute("SELECT crc32 FROM {} WHERE crc32 IS NOT NULL"
                               .format(TABLE))]
        assert values  # physically present
        assert "crc32" not in ALGORITHM_COLUMN
        assert "crc32" not in SUPPORTED_ALGORITHMS
    finally:
        conn.close()
