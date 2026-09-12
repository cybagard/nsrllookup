"""Fixture deploy smoke: boot -> /health ready + /check known (Seam 1).

The demoable terminal slice for ticket 08. A fixture Hash Set and its
Provisioning manifest are written into a temporary data dir exactly as the
Provisioner would, then the service is booted through ``bootstrap`` -- the same
entry the container's ``__main__`` runs -- and driven through Flask's test
client. No live server and no real-data download are involved: the smoke proves
the deploy path on fixtures, while the full ~18 GiB Minimal Set and the
production deploy stay operator steps.
"""

import app
import boot
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
DBHASH = "deadbeef"
RELEASE = "2026.03.1"
DELTA = "2026.06.1"


def _provision_volume(data_dir):
    """Write a real-layout fixture Hash Set + its manifest into the data dir."""
    hasheset.build_minimal_fixture_db(
        str(data_dir / "rds.db"),
        [{"crc32": "2E19F1E7", "md5": KNOWN_MD5,
          "sha1": None, "sha256": None,
          "file_name": "known.bin", "file_size": 11,
          "package_id": 0}])
    (data_dir / "manifest.json").write_text(
        '{"set": "modern", "release": "2026.03.1", '
        '"deltas": ["2026.06.1"], "dbhash": "deadbeef"}')


def test_boot_report_ready_and_known_with_dbhash(tmp_path):
    """Boot -> /health ready and /check known, with dbhash in dataset."""
    data_dir = tmp_path / "data"
    audit_dir = tmp_path / "audit"
    data_dir.mkdir()
    audit_dir.mkdir()
    _provision_volume(data_dir)
    try:
        hash_set, manifest = boot.bootstrap(
            str(data_dir), str(audit_dir))
        assert manifest is not None
        assert hash_set is not None
        assert hash_set.provenance.dbhash == DBHASH

        client = app.api.test_client()

        health = client.get("/health").get_json()
        assert health["ready"] is True
        assert health["dataset"] == {
            "set": "modern", "release": RELEASE,
            "deltas": [DELTA], "dbhash": DBHASH}

        check = client.post(
            "/check",
            json={"algorithm": "md5",
                  "hashes": [KNOWN_MD5]}).get_json()
        result = check["results"][0]
        assert result["status"] == "known"
        assert result["dataset"] == {
            "set": "modern", "release": RELEASE,
            "deltas": [DELTA], "dbhash": DBHASH}
    finally:
        app.configure(None)
        app.configure_audit(boot.AuditTrail())


def test_boot_without_volume_is_not_ready(tmp_path):
    """An unprovisioned volume boots not-ready: /check refuses to serve."""
    data_dir = tmp_path / "data"
    audit_dir = tmp_path / "audit"
    data_dir.mkdir()
    audit_dir.mkdir()
    try:
        hash_set, manifest = boot.bootstrap(
            str(data_dir), str(audit_dir))
        assert hash_set is None
        assert manifest is None

        client = app.api.test_client()
        assert client.get("/health").get_json()["ready"] is False
        response = client.post(
            "/check",
            json={"algorithm": "md5",
                  "hashes": [KNOWN_MD5]})
        assert response.status_code == 503
        assert "results" not in response.get_json()
    finally:
        app.configure(None)
        app.configure_audit(boot.AuditTrail())
