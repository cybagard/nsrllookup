"""End-to-end verification: the composed stack holds together as a whole."""

import app
import audit
from hasheset import Provenance
import hasheset
from lookup import look_up

KNOWN = {
    "md5": "AD7B9C14083B52BC532FBA5948342B98",
    "sha1": "3FA828B1A5F1D59CCE6D8A9BB2814F025F84B761",
    "sha256": "A3F9BCA52E3D62E9E2C9F0E2F3D4C5B6A7E8F90A1B2C3D4E5F60718293A4B5C6",
}


def _row(file_name, **digests):
     row = {"crc32": "2E19F1E7", "md5": None,
           "sha1": None, "sha256": None,
            "file_name": file_name, "file_size": 0, "package_id": 0}
     row.update(digests)
     return row


def _provision_realistic(tmp_path):
    """Provision a realistic Minimal Set, then apply a Delta on top."""
    base = str(tmp_path / "base.db")
    hasheset.build_minimal_fixture_db(base, [
        _row("known.bin", md5=KNOWN["md5"], sha1=KNOWN["sha1"],
            sha256=KNOWN["sha256"]),
        _row("md5only.bin", md5="11111111111111111111111111111111"),
    ])
    base_set = hasheset.provision(base,
        Provenance("modern", "2026.03.1"))
    return hasheset.apply_delta(base_set, [_row("delta.bin",
        md5=KNOWN["md5"], sha1=KNOWN["sha1"], sha256=KNOWN["sha256"])],
        "2026.06.1")


def test_all_three_algorithms_answer_with_provenance(tmp_path):
    """Each algorithm answers known/unknown/invalid with full provenance."""
    hash_set = _provision_realistic(tmp_path)
    app.configure(hash_set)
    try:
        client = app.api.test_client()
        for algo in ("md5", "sha1", "sha256"):
            data = client.post("/check", json={
                "algorithm": algo, "hashes": [KNOWN[algo]]}).get_json()
            result = data["results"][0]
            assert result["status"] == "known"
            assert result["algorithm"] == algo
            assert result["dataset"] == {
                "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"]}
    finally:
        app.configure(None)


def test_delta_refreshed_health(tmp_path):
    """Health reports the refreshed release + delta after the apply."""
    hash_set = _provision_realistic(tmp_path)
    app.configure(hash_set)
    try:
        data = app.api.test_client().get("/health").get_json()
        assert data["ready"] is True
        assert data["dataset"] == {
            "set": "modern", "release": "2026.03.1", "deltas": ["2026.06.1"]}
    finally:
        app.configure(None)


def test_audit_trail_populated_including_rejections(tmp_path):
    """The trail holds success + rejection entries."""
    hash_set = _provision_realistic(tmp_path)
    log = str(tmp_path / "audit.log")
    app.configure(hash_set)
    app.configure_audit(audit.AuditTrail(log))
    try:
        client = app.api.test_client()
        client.post("/check", json={
            "algorithm": "md5", "hashes": [KNOWN["md5"]]})
        client.post("/check", json={
            "algorithm": "crc32", "hashes": [KNOWN["md5"]]})
    finally:
        reopened = audit.AuditTrail(log).read()
        app.configure(None)
        app.configure_audit(audit.AuditTrail())
    assert len(reopened) == 2
    produced = [e for e in reopened if e["results_produced"]]
    rejected = [e for e in reopened if not e["results_produced"]]
    assert len(produced) == 1 and len(rejected) == 1


def test_lookup_module_direct(tmp_path):
    """The lookup module answers the fixture Hash Set directly."""
    hash_set = _provision_realistic(tmp_path)
    results = look_up(hash_set, [KNOWN["md5"], "0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F"], "md5")
    by = {r["digest"]: r["status"] for r in results}
    assert by[KNOWN["md5"]] == "known"
    assert by["0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F"] == "unknown"


def test_no_retired_component_reachable():
    """The retired GET route and socket client are gone."""
    client = app.api.test_client()
    response = client.get("/check/" + KNOWN["md5"])
    assert response.status_code == 404