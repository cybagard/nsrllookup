"""Provisioner smoke checks (Seam 3, I/O-bound, out-of-CI).

The Provisioner verifies a released archive in three layers (zip SHA-1
sidecar, inner SHA-256 signatures, NIST dbhash), applies the ordered
deltas, and writes the queryable Hash Set, Sidecar index, and
Provisioning manifest. These checks exercise that flow on a tiny
fixture, with the dbhash layer injected (ADR-0006). Layer 3 coexists in
two forms: the compute-and-compare `verify_dbhash` (the fixture stand-in)
and the record-and-attest `read_published_dbhash` / `provision_record`
path that reads NIST's published token from `dbhashes.txt` (the turnkey
path). Real multi-giB data stays an operator step.
"""

import hashlib
import urllib.error

from hasheset import build_delta_sql
from hasheset import build_minimal_fixture_db
from hasheset import verify_readiness

from provision import FetchError
from provision import fetch_plan
from provision import fetch_set
from provision import provision
from provision import provision_record
from provision import read_manifest
from provision import read_published_dbhash
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


def test_provisioned_set_passes_readiness_gate(tmp_path):
    """The written manifest matches the returned set's provenance (gate)."""
    base = tmp_path / "base.db"
    _base_db(base)
    manifest = tmp_path / "manifest.json"
    set_obj, _record = provision(
        str(base), "modern", "2026.03.1", [],
        published_dbhash="deadbeef", dbhash=lambda _p: "deadbeef",
        manifest_path=manifest)
    assert verify_readiness(read_manifest(manifest), set_obj) is True
    assert set_obj.provenance.dbhash == "deadbeef"


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


def _dbhashes_file(path, lines):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def test_read_published_token_for_release(tmp_path):
    """Layer 3: NIST's published `dbhash` is read for the Release's db."""
    path = tmp_path / "dbhashes.txt"
    _dbhashes_file(path, [
        "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
        " RDS_2026.09.1_modern_minimal.db",
        "1. RDS_2026.03.1_modern_minimal.db",
        "052bcc035295296713cd4704717cdfe58924a211"
        " RDS_2026.09.1_legacy.db",
    ])
    assert read_published_dbhash(
        path, "RDS_2026.09.1_modern_minimal.db") == (
        "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a")
    assert read_published_dbhash(
        path, "RDS_2026.09.1_legacy.db") == (
        "052bcc035295296713cd4704717cdfe58924a211")


def test_read_published_token_absent(tmp_path):
    """Layer 3: a db object NIST did not publish is not recorded."""
    path = tmp_path / "dbhashes.txt"
    _dbhashes_file(path, [
        "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
        " RDS_2026.09.1_modern_minimal.db",
    ])
    assert read_published_dbhash(path, "RDS_nope.db") is None


def test_record_attests_published_token(tmp_path):
    """Turnkey layer 3 records NIST's published token in the manifest."""
    base = tmp_path / "base.db"
    _base_db(base)
    hash_file = tmp_path / "dbhashes.txt"
    _dbhashes_file(hash_file, [
        "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
        " RDS_2026.09.1_modern_minimal.db",
    ])
    manifest = tmp_path / "manifest.json"
    new_md5 = hashlib.md5(b"delta file").hexdigest().upper()
    set_obj, record = provision_record(
        str(base), "modern", "2026.09.1",
        [("2026.09.1", _delta_sql(new_md5))],
        "RDS_2026.09.1_modern_minimal.db", hash_file, manifest)
    assert record["deltas"] == ["2026.09.1"]
    assert record["dbhash"] == "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
    assert (
        set_obj.provenance.dbhash == "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a")
    assert read_manifest(manifest) == record


def test_record_refuses_missing_token(tmp_path):
    """Turnkey layer 3 refuses when NIST published no token for the db."""
    base = tmp_path / "base.db"
    _base_db(base)
    hash_file = tmp_path / "dbhashes.txt"
    _dbhashes_file(hash_file, [
        "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
        " RDS_2026.09.1_modern_minimal.db",
    ])
    manifest = tmp_path / "manifest.json"
    try:
        provision_record(
            str(base), "modern", "2026.09.1", [],
            "RDS_unpublished.db", hash_file, manifest)
    except ValueError:
        return
    raise AssertionError("expected missing published token to be refused")


# --- Fetch stage: the turnkey driver pulls NIST's objects by exact name ---

_NIST_BASE = "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS"


class _Handle:
     # A stand-in for urllib's opened object: a context manager with .read().
    def __init__(self, content):
        self._content = content

    def read(self):
        return self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_opener(store):
     # A stub network: return bytes for a known object, refuse a miss.
    def opener(url):
        if url not in store:
            raise urllib.error.URLError("no such object: " + url)
        return _Handle(store[url])
    return opener


def test_plan_derives_object_names_from_identifiers():
     # Fetch probes exact names derived from the identifiers, not URLs.
    plan = fetch_plan("2026.09.1", ["2026.06.1", "2026.03.1"], "/tmp/x")
    roles = [role for role, *_ in plan]
    assert roles == [
         "release_zip", "release_sidecar", "delta_zip", "delta_sidecar",
         "delta_zip", "delta_sidecar", "dbhashes", "signatures"
     ]
    urls = [url for _role, _marker, url, _target in plan]
     # No URL is hard-coded; each carries the per-Release path rds_<id>/.
    assert any("/rds_2026.09.1/" in url for url in urls)
    assert "/rds_2026.03.1/" in urls[4]
    assert any(url.endswith("dbhashes.txt") for url in urls)
    assert any(url.endswith("signatures.txt") for url in urls)
    assert "RDS_2026.09.1_modern_minimal.zip" in urls[0]
    assert "RDS_2026.03.1_modern_minimal_delta.zip" in urls[4]


def test_fetch_set_pulls_release_and_deltas(tmp_path):
     # The driver fetches the full Release + ordered Deltas + sidecars.
    dest = tmp_path / "download"
    base = _NIST_BASE
    store = {
        base + "/rds_2026.09.1/RDS_2026.09.1_modern_minimal.zip":
            b"full-release",
        base + "/rds_2026.09.1/"
             "RDS_2026.09.1_modern_minimal.zip.sha": b"SHA1=deadbeef\n",
        base + "/rds_2026.06.1/RDS_2026.06.1_modern_minimal_delta.zip":
            b"delta-06",
        base + "/rds_2026.06.1/"
             "RDS_2026.06.1_modern_minimal_delta.zip.sha": b"SHA1=cafe\n",
        base + "/rds_2026.03.1/RDS_2026.03.1_modern_minimal_delta.zip":
            b"delta-03",
        base + "/rds_2026.03.1/"
             "RDS_2026.03.1_modern_minimal_delta.zip.sha": b"SHA1=feed\n",
        base + "/rds_2026.09.1/dbhashes.txt": b"db",
        base + "/rds_2026.09.1/signatures.txt": b"sigs",
     }
    fetched = fetch_set(
         "2026.09.1", ["2026.06.1", "2026.03.1"], dest,
        base=base, opener=_fake_opener(store))
    assert fetched.release_zip.read_bytes() == b"full-release"
    assert fetched.release_sidecar.read_bytes() == b"SHA1=deadbeef\n"
    assert [delta.release for delta in fetched.deltas] == (
         ["2026.06.1", "2026.03.1"])
    assert fetched.deltas[0].zip.read_bytes() == b"delta-06"
    assert fetched.deltas[0].sidecar.read_bytes() == b"SHA1=cafe\n"
    assert fetched.deltas[1].zip.read_bytes() == b"delta-03"
    assert fetched.dbhashes.read_bytes() == b"db"
    assert fetched.signatures.read_bytes() == b"sigs"


def test_fetch_missing_object_surfaces(tmp_path):
     # A missing object refuses loudly (no silent empty fetch).
    dest = tmp_path / "download"
    base = _NIST_BASE
    store = {
        base + "/rds_2026.09.1/RDS_2026.09.1_modern_minimal.zip":
            b"full-release",
        base + "/rds_2026.09.1/"
             "RDS_2026.09.1_modern_minimal.zip.sha": b"SHA1=deadbeef\n",
     }
    try:
        fetch_set(
             "2026.09.1", [], dest, base=base,
            opener=_fake_opener(store))
    except FetchError:
        return
    raise AssertionError("expected a missing object to raise FetchError")


def test_fetch_writes_only_when_object_present(tmp_path):
     # A miss leaves no partial object written for the failed probe.
    dest = tmp_path / "download"
    try:
        fetch_set(
             "2026.09.1", [], dest, base=_NIST_BASE,
            opener=_fake_opener({}))
    except FetchError:
        pass
    assert not (dest / "RDS_2026.09.1_modern_minimal.zip").exists()
