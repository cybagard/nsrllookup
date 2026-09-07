"""Provisioner smoke checks (Seam 3, I/O-bound, out-of-CI).

The Provisioner verifies a released archive in three layers (zip SHA-1 sidecar,
inner SHA-256 signatures, NIST dbhash), applies the ordered deltas, and writes the
queryable Hash Set, Sidecar index, and Provisioning manifest. These checks exercise
that flow on a tiny fixture, with the dbhash layer injected (ADR-0006). Real
multi-giB data stays an operator step.
"""

import hashlib

from hasheset import build_delta_sql
from hasheset import build_minimal_fixture_db

from provision import provision
from provision import read_manifest
from provision import verify_dbhash
from provision import verify_signatures
from provision import verify_zip_sha
from provision import write_manifest


def _sha_sidecar(path, digest):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("SHA1(" + path.name + ")= " + digest + "\n")


def _signatures_file(path, entries):
    lines = ["SHA256(" + n + ")= " + h for n, h in entries]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base_db(path):
    build_minimal_fixture_db(
        str(path), [
        {"crc32": None, "md5": "11111111111111111111111111111111",
        "sha1": None, "sha256": None, "file_name": "base.bin",
        "file_size": 0, "package_id": 0},
        ])


def _delta_sql(md5):
    row = {"crc32": None, "md5": md5, "sha1": None, "sha256": None,
        "file_name": "delta.bin", "file_size": 0, "package_id": 0}
    return build_delta_sql([row])


def test_zip_sha_matches_sidecar(tmp_path):
    """Layer 1: the zip SHA-1 matches its sidecar."""
    zip_path = tmp_path / "release.zip"
    zip_path.write_bytes(b"some bytes")
    sidecar = tmp_path / "release.zip.sha"
    _sha_sidecar(sidecar, hashlib.sha1(b"some bytes").hexdigest())
    assert verify_zip_sha(zip_path, sidecar) is True


def test_zip_sha_detects_tamper(tmp_path):
    """Layer 1: a zip that does not match its sidecar is refused."""
    zip_path = tmp_path / "release.zip"
    zip_path.write_bytes(b"tampered bytes")
    sidecar = tmp_path / "release.zip.sha"
    _sha_sidecar(sidecar, "0" * 40)
    assert verify_zip_sha(zip_path, sidecar) is False


def test_zip_sha_refuses_unparseable_sidecar(tmp_path):
    """Layer 1: a sidecar with no parseable value is refused."""
    zip_path = tmp_path / "release.zip"
    zip_path.write_bytes(b"some bytes")
    sidecar = tmp_path / "release.zip.sha"
    with open(sidecar, "w", encoding="utf-8") as handle:
        handle.write("garbage with no digest\n")
    assert verify_zip_sha(zip_path, sidecar) is False


def test_signatures_match_all_inner_files(tmp_path):
    """Layer 2: every listed inner file matches signatures.txt."""
    signed = tmp_path / "signed"
    signed.mkdir()
    delta = signed / "delta.sql"
    schema = signed / "schema.sql"
    delta.write_bytes(b"INSERT INTO FILE ...")
    schema.write_bytes(b"CREATE TABLE FILE ...")
    entries = [("delta.sql", _sha256(delta)),
        ("schema.sql", _sha256(schema))]
    _signatures_file(tmp_path / "signatures.txt", entries)
    assert verify_signatures(signed, tmp_path / "signatures.txt") is True


def test_signatures_detect_tamper(tmp_path):
    """Layer 2: one altered inner file is refused."""
    signed = tmp_path / "signed"
    signed.mkdir()
    delta = signed / "delta.sql"
    schema = signed / "schema.sql"
    delta.write_bytes(b"tampered")
    schema.write_bytes(b"CREATE TABLE FILE ...")
    sigs = tmp_path / "signatures.txt"
    _signatures_file(sigs, [
        ("delta.sql", _sha256(schema)),
        ("schema.sql", _sha256(schema)),
    ])
    assert verify_signatures(signed, sigs) is False


def test_signatures_missing_file_is_refused(tmp_path):
    """Layer 2: a listed file that is absent is refused."""
    signed = tmp_path / "signed"
    signed.mkdir()
    sigs = tmp_path / "signatures.txt"
    _signatures_file(sigs, [("delta.sql", "0" * 64)])
    assert verify_signatures(signed, sigs) is False


def test_signatures_skips_non_matching_lines(tmp_path):
    """Layer 2: blank/comment lines are skipped; good ones verify."""
    signed = tmp_path / "signed"
    signed.mkdir()
    delta = signed / "delta.sql"
    delta.write_bytes(b"INSERT")
    sigs = tmp_path / "signatures.txt"
    with open(sigs, "w", encoding="utf-8") as handle:
        handle.write("# a comment line\n")
        handle.write("\n")
        handle.write("SHA256(delta.sql)= " + _sha256(delta) + "\n")
    assert verify_signatures(signed, sigs) is True


def test_dbhash_matches_published(tmp_path):
    """Layer 3: the computed dbhash equals the published target."""
    db_path = tmp_path / "rds.db"
    db_path.write_bytes(b"the-final-database-bytes")
    assert verify_dbhash(db_path, _sha256(db_path), _sha256) is True


def test_dbhash_mismatch_refused(tmp_path):
    """Layer 3: a dbhash that differs from the target is refused."""
    db_path = tmp_path / "rds.db"
    db_path.write_bytes(b"the-final-database-bytes")
    assert verify_dbhash(db_path, "0" * 64, _sha256) is False


def test_manifest_round_trips(tmp_path):
    """The Provisioning manifest is written and read back unchanged."""
    path = tmp_path / "manifest.json"
    written = write_manifest(
        path, "modern", "2026.03.1",
        ["2026.06.1", "2026.09.1"], "deadbeef")
    expected = {
        "set": "modern", "release": "2026.03.1",
        "deltas": ["2026.06.1", "2026.09.1"], "dbhash": "deadbeef",
    }
    assert read_manifest(path) == written == expected


def test_provision_applies_deltas_and_writes_manifest(tmp_path):
    """Provisioning applies the ordered Deltas and writes the manifest."""
    base = tmp_path / "base.db"
    _base_db(base)
    new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
    manifest = tmp_path / "manifest.json"
    set_obj, record = provision(
        str(base), "modern", "2026.03.1",
        [("2026.06.1", _delta_sql(new_md5))],
        published_dbhash="deadbeef",
        dbhash=lambda _p: "deadbeef",
        manifest_path=manifest)
    assert record["deltas"] == ["2026.06.1"]
    assert record["dbhash"] == "deadbeef"
    assert set_obj.is_known("md5", new_md5)
    assert read_manifest(manifest) == record


def test_provision_refuses_on_dbhash_mismatch(tmp_path):
    """Provisioning refuses when the final dbhash differs from NIST."""
    base = tmp_path / "base.db"
    _base_db(base)
    manifest = tmp_path / "manifest.json"
    try:
        provision(
            str(base), "modern", "2026.03.1", [],
            published_dbhash="deadbeef", dbhash=lambda _p: "cafebabe",
            manifest_path=manifest)
    except ValueError:
        return
    raise AssertionError("expected dbhash mismatch to be refused")
