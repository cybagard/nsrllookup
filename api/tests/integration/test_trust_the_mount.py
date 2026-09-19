"""Trust-the-mount regression guards (ADR-0006, ro-mount-guard ticket 01).

A booted or re-checked volume opens the mounted **Hash Set** **read-only** and
must **never rebuild its per-Algorithm hash index** at boot time -- the
**Provisioner** and **Delta** apply build the index, not container boot and
``make verify``. Nothing asserts the negative today: the deploy smoke
provisions into a writable temp dir and never forces index-build to fail, so a
writable-connect / index-rebuild path could creep back into a read-the-mount
entry point and the suite would stay green. These two guards close that hole,
so any re-introduction turns the suite red.

- the **white-box** guard is OS-portable and runs in CI: it forces the
  index-build entries to fail with an ``AssertionError`` naming the invariant
  and asserts both **boot** and ``verify`` still succeed;
- the **read-only-volume** guard is the faithful reproduction of the original
  failure (a writable ``CREATE INDEX`` would open a journal in the data dir
  and fail): it provisions an indexed volume, makes the data dir **read-only**,
  and asserts **boot** and ``verify`` still succeed -- POSIX-only, skipped on
  Windows and as root, where a read-only *dir* does not force the failure.
"""

import os
import stat

import pytest

import app
import boot
import driver
import hasheset

KNOWN_MD5 = "AD7B9C14083B52BC532FBA5948342B98"
DBHASH = "deadbeef"


def _ro_dir_skip_reason():
    # A read-only *dir* forces the failure on POSIX, for a non-root writer.
    if os.name != "posix":
        return "read-only-dir guard is POSIX-only; skipped on Windows"
    if os.geteuid() == 0:
        return "a read-only dir does not force the failure as root"
    return None


RO_DIR_SKIP = _ro_dir_skip_reason()


def _provision_volume(data_dir):
    """Write the real-layout fixture Hash Set, its index, its manifest.

    The same shape the Provisioner leaves in a data dir: an indexed ``rds.db``
    plus the Provisioning manifest that attests its identity, so a no-rebuild
    boot against this fixture stays faithful to what the Provisioner writes.
    """
    hasheset.build_minimal_fixture_db(
        str(data_dir / "rds.db"),
        [{"crc32": "2E19F1E7", "md5": KNOWN_MD5,
          "sha1": None, "sha256": None,
          "file_name": "known.bin", "file_size": 11,
          "package_id": 0}])
    hasheset.build_hash_index(str(data_dir / "rds.db"))
    (data_dir / "manifest.json").write_text(
        '{"set": "modern", "release": "2026.03.1", '
        '"deltas": ["2026.06.1"], "dbhash": "deadbeef"}')


def _refuse_index_build(*_args, **_kwargs):
    # Any index-build entry the read-the-mount path reaches is a regression.
    raise AssertionError("boot/verify must not rebuild the index")


def test_boot_and_verify_never_rebuild_index(tmp_path, monkeypatch):
    """White-box guard: forcing index-build to fail must not break boot/
    verify -- they load the mount read-only and trust its index."""
    data_dir = tmp_path / "data"
    audit_dir = tmp_path / "audit"
    data_dir.mkdir()
    audit_dir.mkdir()
    _provision_volume(data_dir)
    monkeypatch.setattr(hasheset, "build_hash_index", _refuse_index_build)
    monkeypatch.setattr(hasheset, "provision", _refuse_index_build)
    monkeypatch.setattr(hasheset, "_rebuild_index", _refuse_index_build)
    try:
        hash_set, manifest = boot.bootstrap(
            str(data_dir), str(audit_dir))
        assert manifest is not None
        assert hash_set is not None
        assert hash_set.provenance.dbhash == DBHASH
        assert app.api.test_client().get("/health").get_json()["ready"] \
            is True

        result = driver.verify_release(str(data_dir))
        assert result.ready is True
        assert result.checks["well_formed"] is True
    finally:
        app.configure(None)
        app.configure_audit(boot.AuditTrail())


@pytest.mark.skipif(RO_DIR_SKIP is not None, reason=RO_DIR_SKIP or "")
def test_read_only_volume_still_boots_and_verifies(tmp_path):
    """Read-only-dir guard: a read-only data dir still boots ready and
    verifies ready -- boot/verify never need a writable mount."""
    data_dir = tmp_path / "data"
    audit_dir = tmp_path / "audit"
    data_dir.mkdir()
    audit_dir.mkdir()
    _provision_volume(data_dir)
    original_mode = stat.S_IMODE(data_dir.stat().st_mode)
    os.chmod(data_dir, 0o555)
    try:
        hash_set, manifest = boot.bootstrap(
            str(data_dir), str(audit_dir))
        assert manifest is not None
        assert hash_set is not None
        assert hash_set.is_known("md5", KNOWN_MD5)
        assert app.api.test_client().get("/health").get_json()["ready"] \
            is True

        result = driver.verify_release(str(data_dir))
        assert result.ready is True
    finally:
        os.chmod(data_dir, original_mode)
        app.configure(None)
        app.configure_audit(boot.AuditTrail())
