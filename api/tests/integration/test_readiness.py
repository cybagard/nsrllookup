"""Readiness gate: the service is ready only when its manifest agrees.

Seam 1 plus the boot-time gate (ADR-0005). A present, matched
**Provisioning manifest** makes the service **ready** and its answers carry
the final **dbhash**; a missing or mismatched manifest makes it **not-ready**,
so a stale or unverified volume answers nothing.
"""

import app
from hasheset import Provenance
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
DBHASH = "deadbeef"


def _provision(tmp_path):
    path = str(tmp_path / "fixtureset.db")
    hasheset.build_minimal_fixture_db(path, [
             {"crc32": "2E19F1E7", "md5": KNOWN_MD5,
                "sha1": None, "sha256": None,
                "file_name": "known.bin", "file_size": 11,
                 "package_id": 0},
             ])
    return hasheset.provision(path,
            Provenance("modern", "2026.03.1", ["2026.06.1"], DBHASH))


def test_ready_when_manifest_matches(tmp_path):
    """A present, matching manifest makes /check ready with dbhash."""
    hash_set = _provision(tmp_path)
    manifest = {"set": "modern", "release": "2026.03.1",
                "deltas": ["2026.06.1"], "dbhash": DBHASH}
    app.configure(hash_set, manifest)
    try:
        client = app.api.test_client()
        health = client.get("/health").get_json()
        assert health["ready"] is True
        assert health["dataset"]["dbhash"] == DBHASH
        data = client.post("/check",
                           json={"algorithm": "md5",
                                    "hashes": [KNOWN_MD5]}).get_json()
        assert data["results"][0]["status"] == "known"
        assert data["results"][0]["dataset"]["dbhash"] == DBHASH
    finally:
        app.configure(None)


def test_not_ready_when_manifest_absent(tmp_path):
    """No manifest means not-ready, so /check refuses to serve."""
    hash_set = _provision(tmp_path)
    app.configure(hash_set, None)
    try:
        client = app.api.test_client()
        assert client.get("/health").get_json()["ready"] is False
        response = client.post("/check",
                               json={"algorithm": "md5",
                                        "hashes": [KNOWN_MD5]})
        assert response.status_code == 503
        assert "results" not in response.get_json()
    finally:
        app.configure(None)


def test_not_ready_when_dbhash_mismatched(tmp_path):
    """A manifest whose dbhash no longer matches makes the service not-ready."""
    hash_set = _provision(tmp_path)
    manifest = {"set": "modern", "release": "2026.03.1",
                "deltas": ["2026.06.1"], "dbhash": "cafebabe"}
    app.configure(hash_set, manifest)
    try:
        client = app.api.test_client()
        assert client.get("/health").get_json()["ready"] is False
        response = client.post("/check",
                               json={"algorithm": "md5",
                                        "hashes": [KNOWN_MD5]})
        assert response.status_code == 503
    finally:
        app.configure(None)
