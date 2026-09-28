"""Seam 2, driven in the shape the service actually deploys: the Hash Set
is opened once at boot, and every **Lookup Session** is answered on a
waitress **worker thread**.

The rest of the suite serves through the single-threaded Flask test client,
which can never produce the deployed shape -- so no test there could ever
see a connection that refuses to answer off its boot thread. These drive the
public ``look_up`` interface exactly as the deployment does (opened at boot
on one thread, consulted from another, and from several at once) and assert
one **Lookup Result** per Digest with the right
**Known/Unknown/Invalid** **status** and the full **provenance** the
answering dataset carries. The connection's own mechanics (how it crosses
threads) are not the object of assertion.
"""

import threading

import pytest

from hasheset import Provenance
from hasheset import build_minimal_fixture_db
from hasheset import provision
from lookup import look_up

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
UNKNOWN_MD5 = "2977520A5C5FAAD2286D58675E400412"
MALFORMED = "not-a-digest"


@pytest.fixture
def hash_set(tmp_path):
    # The mount as the Provisioner left it: provisioned in-band, then the
    # service opens it -- here on the main thread, as boot does.
    path = str(tmp_path / "fixtureset.db")
    build_minimal_fixture_db(path, [
          {"crc32": "2E19F1E7", "md5": KNOWN_MD5,
           "sha1": None, "sha256": None, "file_name": "known.bin",
            "file_size": 11, "package_id": 0},
       ])
    return provision(path, Provenance("modern", "2026.03.1", ["2026.06.1"],
                                      "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"))


def _run_session(hash_set, digests, algorithm, out, errors):
    # One Lookup Session on a worker thread; results/errors land in the lists.
    try:
        out.append((algorithm, look_up(hash_set, digests, algorithm)))
    except Exception as exc:  # noqa: BLE001 -- the session must not die
        errors.append(repr(exc))


def test_lookup_serves_from_a_worker_thread(hash_set):
    out, errors = [], []
    _run_session(hash_set, [KNOWN_MD5, UNKNOWN_MD5, MALFORMED], "md5",
                 out, errors)
    assert errors == []
    _algorithm, results = out[0]
    by_digest = {r["digest"]: r for r in results}
    assert by_digest[KNOWN_MD5]["status"] == "known"
    assert by_digest[UNKNOWN_MD5]["status"] == "unknown"
    assert by_digest[MALFORMED.upper()]["status"] == "invalid"
    for result in results:
        assert result["dataset"] == {
              "set": "modern",
              "release": "2026.03.1",
              "deltas": ["2026.06.1"],
              "dbhash": "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a",
          }


def test_concurrent_lookup_sessions_are_all_correct(hash_set):
    # Several waitress workers answering the same provisioned Hash Set at
    # once: every Digest must still get the right answer.
    workers = 8
    rounds = 25
    out, errors = [], []
    barrier = threading.Barrier(workers)

    def session():
        barrier.wait()
        for _ in range(rounds):
            _run_session(hash_set, [KNOWN_MD5, UNKNOWN_MD5], "md5",
                         out, errors)

    threads = [threading.Thread(target=session) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(out) == workers * rounds
    for _algorithm, results in out:
        by_digest = {r["digest"]: r for r in results}
        assert by_digest[KNOWN_MD5]["status"] == "known"
        assert by_digest[UNKNOWN_MD5]["status"] == "unknown"
