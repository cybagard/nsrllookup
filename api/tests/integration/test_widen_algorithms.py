"""Seam 1: SHA-1 & SHA-256 are first-class, and **Known** is per-Algorithm.

The index, ``look_up``, and ``POST /check`` all accept SHA-1 and SHA-256
alongside MD5. A digest that is **Known** under one **Algorithm** is not
reported **Known** under another for the same value, and a SHA-256 that NIST
deduplicates across many files still resolves to a single **Known** answer.
"""

import json

import app
from hasheset import Provenance
import hasheset
from lookup import look_up

KNOWN = {
       "md5": "AD7B9C14083B52BC532FBA5948342B98",
       "sha1": "3FA828B1A5F1D59CCE6D8A9BB2814F025F84B761",
       "sha256": "A3F9BCA52E3D62E9E2C9F0E2F3D4C5B6A7E8F90A1B2C3D4E5F60718293A4B5C6",
 }


def _provision(path, deltas=("2026.06.1",)):
    return hasheset.provision(path,
          Provenance("modern", "2026.03.1", list(deltas)))


def _results(client, algorithm, raw_digests):
    response = client.post('/check',
          json={'algorithm': algorithm, 'hashes': raw_digests})
    assert response.status_code == 200
    return json.loads(response.get_data(as_text=True))['results']


def test_index_is_built_for_all_three_algorithms(tmp_path):
    """The per-Algorithm index exists for MD5, SHA-1 and SHA-256."""
    path = str(tmp_path / "fixtureset.db")
    hasheset.build_minimal_fixture_db(path, [
            {"crc32": "2E19F1E7", "md5": KNOWN["md5"],
              "sha1": KNOWN["sha1"], "sha256": KNOWN["sha256"],
               "file_name": "known.bin", "file_size": 11,
                "package_id": 0},
        ])
    hash_set = _provision(path)
    assert set(hasheset.SUPPORTED_ALGORITHMS) == {"md5", "sha1", "sha256"}
    assert hash_set.is_known("md5", KNOWN["md5"])
    assert hash_set.is_known("sha1", KNOWN["sha1"])
    assert hash_set.is_known("sha256", KNOWN["sha256"])


def test_sha1_and_sha256_lookup_via_http(tmp_path):
    """SHA-1 and SHA-256 are accepted by POST /check, in any case."""
    path = str(tmp_path / "fixtureset.db")
    hasheset.build_minimal_fixture_db(path, [
            {"crc32": "2E19F1E7", "md5": KNOWN["md5"],
              "sha1": KNOWN["sha1"], "sha256": KNOWN["sha256"],
               "file_name": "known.bin", "file_size": 11,
                "package_id": 0},
        ])
    hset = _provision(path)
    app.configure(hset, hset.provenance.dataset())
    try:
        client = app.api.test_client()
        assert _results(client, 'sha1', [KNOWN['sha1']])[0]['status'] == 'known'
        assert _results(client, 'sha256', [KNOWN['sha256']])[0]['status'] == 'known'
        lowered = [KNOWN['sha256'].lower()]
        assert _results(client, 'sha256', lowered)[0]['status'] == 'known'
    finally:
        app.configure(None)


def test_known_is_per_algorithm(tmp_path):
    """Being **Known** under MD5 is never **Known** under SHA-256.

    A value that is **Known** under MD5 is not reported **Known** when the
    same value is queried under the SHA-256 **Algorithm** -- the answer is
    always scoped to one **Algorithm**.
    """
    path = str(tmp_path / "fixtureset.db")
    hasheset.build_minimal_fixture_db(path, [
            {"crc32": "2E19F1E7", "md5": "11111111111111111111111111111111",
              "sha1": "A" * 40, "sha256": KNOWN["sha256"],
               "file_name": "a.bin", "file_size": 3, "package_id": 0},
        ])
    hash_set = _provision(path)
    assert look_up(hash_set, ["11111111111111111111111111111111"],
                   'md5')[0]['status'] == 'known'
    assert look_up(hash_set, ["11111111111111111111111111111111"],
                   'sha256')[0]['status'] != 'known'


def test_sha256_dedup_resolves_to_single_known(tmp_path):
    """Two files sharing one NIST-deduplicated sha256 yield one **Known**."""
    shared = KNOWN["sha256"]
    path = str(tmp_path / "dedupset.db")
    hasheset.build_minimal_fixture_db(path, [
            {"crc32": None, "md5": "11111111111111111111111111111111",
              "sha1": None, "sha256": shared,
               "file_name": "file-a.bin", "file_size": 1, "package_id": 0},
            {"crc32": None, "md5": "22222222222222222222222222222222",
              "sha1": None, "sha256": shared,
               "file_name": "file-b.bin", "file_size": 1, "package_id": 0},
        ])
    results = look_up(_provision(path), [shared], 'sha256')
    assert results == [
              {"digest": shared, "algorithm": "sha256", "status": "known",
                "dataset": {"set": "modern", "release": "2026.03.1",
                             "deltas": ["2026.06.1"], "dbhash": None}}
          ]


def test_crc32_rejected_as_algorithm(tmp_path):
    """CRC-32 is physically present but is not a supported lookup
    **Algorithm**."""
    path = str(tmp_path / "fixtureset.db")
    hasheset.build_minimal_fixture_db(path, [
            {"crc32": "2E19F1E7", "md5": KNOWN["md5"],
              "sha1": KNOWN["sha1"], "sha256": KNOWN["sha256"],
               "file_name": "known.bin", "file_size": 11,
                "package_id": 0},
        ])
    app.configure(_provision(path))
    try:
        response = app.api.test_client().post('/check',
                  json={'algorithm': 'crc32', 'hashes': ['2E19F1E7']})
        assert response.status_code == 400
    finally:
        app.configure(None)
