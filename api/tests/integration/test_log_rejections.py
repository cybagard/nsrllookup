"""Seam 1: request-level rejections also produce an Audit Entry.

A request rejected at the request level -- an unsupported Algorithm or a
structurally malformed body -- produces no Lookup Result list, but the
forensic record of a bad request is worth keeping (ADR-0004). A test drives
the rejected request and observes, black-box, that an entry was recorded
noting that no results were produced.
"""

import app
from audit import AuditTrail
from hasheset import Provenance
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"


def _provision(tmp_path):
    path = str(tmp_path / "fixtureset.db")
    hasheset.build_minimal_fixture_db(path, [
              {"crc32": "2E19F1E7", "md5": KNOWN_MD5, "md5sha1": None,
                "sha1": None, "sha256": None, "filename": "known.bin"},
          ])
    return hasheset.provision(path, Provenance("modern", "2026.03.1"))


def test_bad_algorithm_rejection_is_audited(tmp_path):
    """An unsupported Algorithm rejection still writes an Audit Entry."""
    log = str(tmp_path / "audit.log")
    trail = AuditTrail(log)
    app.configure(_provision(tmp_path))
    app.configure_audit(trail)
    try:
        response = app.api.test_client().post('/check',
                      json={'algorithm': 'crc32', 'hashes': [KNOWN_MD5]})
        assert response.status_code == 400
        entries = trail.entries()
        assert len(entries) == 1
        assert entries[0]["results_produced"] is False
        assert entries[0]["results"] is None
        assert entries[0]["algorithm"] == "crc32"
    finally:
        app.configure(None)
        app.configure_audit(AuditTrail())


def test_malformed_body_rejection_is_audited(tmp_path):
    """A malformed-body rejection still writes an Audit Entry."""
    log = str(tmp_path / "audit.log")
    trail = AuditTrail(log)
    app.configure(_provision(tmp_path))
    app.configure_audit(trail)
    try:
        response = app.api.test_client().post('/check', data="not json",
                      content_type='application/json')
        assert response.status_code == 400
        entries = trail.entries()
        assert len(entries) == 1
        assert entries[0]["results_produced"] is False
        assert entries[0]["results"] is None
    finally:
        app.configure(None)
        app.configure_audit(AuditTrail())
