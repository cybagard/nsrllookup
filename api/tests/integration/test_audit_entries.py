"""Seam 1: every Lookup Session produces one Audit Entry (ADR-0004).

The interface is public, so the Audit Trail is the forensic guarantee. A test
points the app at an injectable, file-backed trail, drives a successful
POST /check, and observes -- black-box -- that exactly one Audit Entry was
recorded for it, carrying the timestamp, caller, Algorithm, each Digest +
status, and the Release + Delta releases that answered.
"""

import app
from audit import AuditTrail
from hasheset import Provenance
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
UNKNOWN_MD5 = "2977520A5C5FAAD2286D58675E400412"
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


def test_session_produces_one_audit_entry(tmp_path):
    """A finished session writes exactly one Audit Entry."""
    log = str(tmp_path / "audit.log")
    trail = AuditTrail(log)
    _hs = _provision(tmp_path)
    app.configure(_hs, _hs.provenance.dataset())
    app.configure_audit(trail)
    try:
        response = app.api.test_client().post('/check',
                  json={'algorithm': 'md5', 'hashes': [KNOWN_MD5, UNKNOWN_MD5]})
        assert response.status_code == 200
        assert len(trail.entries()) == 1
    finally:
        app.configure(None)
        app.configure_audit(AuditTrail())


def test_audit_entry_carries_required_fields(tmp_path):
    """One entry: timestamp, caller, algorithm, digests + status, dataset."""
    log = str(tmp_path / "audit.log")
    trail = AuditTrail(log)
    _hs = _provision(tmp_path)
    app.configure(_hs, _hs.provenance.dataset())
    app.configure_audit(trail)
    try:
        app.api.test_client().post('/check',
                  json={'algorithm': 'md5', 'hashes': [KNOWN_MD5, UNKNOWN_MD5]})
        entry = trail.entries()[0]
        assert isinstance(entry["timestamp"], str)
        assert isinstance(entry["caller"], str) and entry["caller"]
        assert entry["algorithm"] == "md5"
        statuses = {r["digest"]: r["status"] for r in entry["results"]}
        assert statuses[KNOWN_MD5] == "known"
        assert statuses[UNKNOWN_MD5] == "unknown"
        assert entry["dataset"] == {"set": "modern", "release": "2026.03.1",
               "deltas": ["2026.06.1"], "dbhash": DBHASH}
    finally:
        app.configure(None)
        app.configure_audit(AuditTrail())


def test_audit_trail_is_durable(tmp_path):
    """Appended entries survive on disk: the trail is durable & append-only."""
    log = str(tmp_path / "audit.log")
    _hs = _provision(tmp_path)
    app.configure(_hs, _hs.provenance.dataset())
    app.configure_audit(AuditTrail(log))
    try:
        client = app.api.test_client()
        client.post('/check', json={'algorithm': 'md5', 'hashes': [KNOWN_MD5]})
        client.post('/check', json={'algorithm': 'md5', 'hashes': [UNKNOWN_MD5]})

        reopened = AuditTrail(log).read()
        assert len(reopened) == 2
        assert reopened[0]["results"][0]["digest"] == KNOWN_MD5
        assert reopened[1]["results"][0]["digest"] == UNKNOWN_MD5
    finally:
        app.configure(None)
        app.configure_audit(AuditTrail())
