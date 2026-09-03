"""Seam 2: the lookup module, tested against the fixture Hash Set.

These assert the mapping from a request (digests + an Algorithm + a Hash Set)
to a list of **Lookup Results** -- with per-item **Known/Unknown/Invalid**
status and full **provenance** -- through the public ``look_up`` function. The
module's SQL/index internals are not touched; only the returned results are.
"""

import pytest

from hasheset import Provenance
from hasheset import provision
from lookup import look_up

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
UNKNOWN_MD5 = "2977520A5C5FAAD2286D58675E400412"


@pytest.fixture
def hash_set(tmp_path):
    path = str(tmp_path / "fixtureset.db")
    from hasheset import build_minimal_fixture_db

    build_minimal_fixture_db(path, [
          {"crc32": "2E19F1E7", "md5": KNOWN_MD5,
           "sha1": None, "sha256": None, "file_name": "known.bin",
            "file_size": 11, "package_id": 0},
       ])
    return provision(path, Provenance("modern", "2026.03.1", ["2026.06.1"]))


def test_one_result_per_digest(hash_set):
    results = look_up(hash_set, [KNOWN_MD5, UNKNOWN_MD5], "md5")
    assert len(results) == 2
    assert [r["digest"] for r in results] == [KNOWN_MD5, UNKNOWN_MD5]


def test_known_and_unknown_statuses(hash_set):
    results = look_up(hash_set, [KNOWN_MD5, UNKNOWN_MD5], "md5")
    by_digest = {r["digest"]: r for r in results}
    assert by_digest[KNOWN_MD5]["status"] == "known"
    assert by_digest[UNKNOWN_MD5]["status"] == "unknown"


def test_invalid_is_distinct_from_unknown(hash_set):
    results = look_up(hash_set, [UNKNOWN_MD5, "zzzz-not-a-digest"], "md5")
    by_digest = {r["digest"]: r for r in results}
    assert by_digest[UNKNOWN_MD5]["status"] == "unknown"
    assert by_digest["ZZZZ-NOT-A-DIGEST"]["status"] == "invalid"


def test_each_result_carries_full_provenance(hash_set):
    result = look_up(hash_set, [KNOWN_MD5], "md5")[0]
    assert result["algorithm"] == "md5"
    assert result["dataset"] == {"set": "modern", "release": "2026.03.1",
                                 "deltas": ["2026.06.1"]}


def test_digests_normalised_to_uppercase(hash_set):
    results = look_up(hash_set, [KNOWN_MD5.lower()], "md5")
    assert results[0]["digest"] == KNOWN_MD5
    assert results[0]["status"] == "known"
