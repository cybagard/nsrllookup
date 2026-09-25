"""Turnkey driver smoke checks (Seam 3, I/O-bound, out-of-CI).

The driver ties the Provisioner together end to end: fetch (ticket 02),
verify three layers, apply the ordered Deltas, record NIST's published
``dbhash`` (ticket 01), and write the queryable Hash Set -- with its
per-Algorithm hash index built into the same database -- plus the
Provisioning manifest. The checks here exercise that orchestration on a
tiny fixture with the fetch *stubbed* (a stand-in ``opener`` returns bytes
for known NIST objects), so the wiring is assertable without the multi-GB
download, which stays the operator's step (ADR-0003).
"""

import hashlib
import io
import tempfile
import urllib.error
import zipfile
from pathlib import Path

import hasheset
from hasheset import build_delta_sql
from hasheset import build_minimal_fixture_db
from hasheset import verify_readiness

from driver import _extract
from driver import _find
from driver import _move_or_copy
from driver import _remove_if_scratch
from driver import apply_delta_releases
from driver import IntegrityError
from driver import provision_release
from driver import verify_release
from provision import read_manifest

_RELEASE = "2026.09.1"
_DELTA_1 = "2026.06.1"
_DELTA_2 = "2026.03.1"
_DBHASH = "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
_BASE = "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS"


def _row(md5, name):
    return {"crc32": None, "md5": md5, "sha1": None, "sha256": None,
             "file_name": name, "file_size": 0, "package_id": 0}


def _inner_signatures(entries):
    lines = ["SHA256(" + n + ")= " + h for n, h in entries]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _sha1_sidecar(name, digest):
    return ("SHA1(" + name + ")= " + digest + "\n").encode("utf-8")


def _zip_bytes(files):
    # Build an NIST-style archive in memory: a tree of inner files.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _build_release_zip(tmp_path):
    # A full-Minimal Release archive: base .db + inner signatures + readme.
    db_path = tmp_path / "base_db.db"
    build_minimal_fixture_db(
        str(db_path),
         [_row("11111111111111111111111111111111", "base.bin")])
    db_bytes = db_path.read_bytes()
    readme = b"modern minimal release readme"
    sigs = _inner_signatures([
          ("rds.db", hashlib.sha256(db_bytes).hexdigest()),
          ("readme.txt", hashlib.sha256(readme).hexdigest())])
    top = "RDS_" + _RELEASE + "_modern_minimal"
    files = {
          top + "/": b"",
          top + "/rds.db": db_bytes,
          top + "/readme.txt": readme,
          top + "/signatures.txt": sigs,
       }
    return _zip_bytes(files)


def _build_delta_zip(tmp_path, delta_release, row):
    # A delta release archive: the ordered .sql + inner signatures + readme.
    sql_text = build_delta_sql([row])
    sql_bytes = sql_text.encode("utf-8")
    readme = b"delta readme"
    top = "RDS_" + delta_release + "_modern_minimal_delta"
    sql_file = "RDS_" + delta_release + "_modern_minimal_delta.sql"
    sigs = _inner_signatures([
           (sql_file, hashlib.sha256(sql_bytes).hexdigest()),
           ("readme.txt", hashlib.sha256(readme).hexdigest())])
    files = {
          top + "/": b"",
          top + "/" + sql_file: sql_bytes,
          top + "/readme.txt": readme,
          top + "/signatures.txt": sigs,
       }
    return _zip_bytes(files)


class _Handle:
    # A stand-in for urllib's opened object: a real stream with .read(size)
    # semantics (b"" at EOF), which the chunked download loop relies on.
    def __init__(self, content):
        self._stream = io.BytesIO(content)

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._stream.close()
        return False


def _fake_opener(store):
    # A stub network: return bytes for a known object, refuse a miss.
    def opener(url):
        if url not in store:
            raise urllib.error.URLError("no such object: " + url)
        return _Handle(store[url])
    return opener


def _store(tmp_path):
    # The NIST objects a real fetch would return, built in memory.
    release_zip = _build_release_zip(tmp_path)
    row_d1 = _row("AAAA4A4A4A4A4A4A4A4A4A4A4A4A4A4A4A", "delta1.bin")
    row_d2 = _row("BBBB4B4B4B4B4B4B4B4B4B4B4B4B4B4B4B", "delta2.bin")
    delta1_zip = _build_delta_zip(tmp_path, _DELTA_1, row_d1)
    delta2_zip = _build_delta_zip(tmp_path, _DELTA_2, row_d2)
    rzip = "RDS_" + _RELEASE + "_modern_minimal.zip"
    d1 = "RDS_" + _DELTA_1 + "_modern_minimal_delta.zip"
    d2 = "RDS_" + _DELTA_2 + "_modern_minimal_delta.zip"
    store = {
           _BASE + "/rds_" + _RELEASE + "/" + rzip: release_zip,
           _BASE + "/rds_" + _RELEASE + "/" + rzip + ".sha":
                _sha1_sidecar(rzip, hashlib.sha1(release_zip).hexdigest()),
           _BASE + "/rds_" + _DELTA_1 + "/" + d1: delta1_zip,
           _BASE + "/rds_" + _DELTA_1 + "/" + d1 + ".sha":
                _sha1_sidecar(d1, hashlib.sha1(delta1_zip).hexdigest()),
           _BASE + "/rds_" + _DELTA_2 + "/" + d2: delta2_zip,
           _BASE + "/rds_" + _DELTA_2 + "/" + d2 + ".sha":
                _sha1_sidecar(d2, hashlib.sha1(delta2_zip).hexdigest()),
         }
    # The plan fetches the terminal release's dbhashes.txt, and the driver
    # looks up the final post-delta db's token in it; terminal depends on the
    # Delta list each test passes, so it is stood up under every release dir
    # carrying the token for every possible final db. There is no top-level
    # signatures.txt object: each zip carries its inner one (layer 2).
    for release in (_RELEASE, _DELTA_1, _DELTA_2):
        lines = "\n".join(
             _DBHASH + " RDS_" + terminal + "_modern_minimal.db"
             for terminal in (_RELEASE, _DELTA_1, _DELTA_2)) + "\n"
        store[_BASE + "/rds_" + release + "/dbhashes.txt"] = lines.encode()
    return store, row_d1, row_d2


def _provision(tmp_path, deltas, *, store):
    return provision_release(
          _RELEASE, deltas,
         data_dir=str(tmp_path / "data"),
         work_dir=str(tmp_path / "work"),
         opener=_fake_opener(store))


def test_provision_applies_deltas_in_order(tmp_path):
    # The turnkey flow applies the ordered Deltas onto the Release.
    store, _row_d1, _row_d2 = _store(tmp_path)
    hash_set, record = _provision(tmp_path, [_DELTA_1], store=store)
    assert record["deltas"] == [_DELTA_1]
    assert record["dbhash"] == _DBHASH
    assert record["set"] == "modern"
    assert record["release"] == _RELEASE
    assert hash_set.is_known("md5", "AAAA4A4A4A4A4A4A4A4A4A4A4A4A4A4A4A")
    assert hash_set.is_known("md5", "11111111111111111111111111111111")
    # Scratch hygiene: the superseded base working copy is gone, the volume
    # in the data dir is what remains (ADR-0003).
    assert not (tmp_path / "work" / "base.db").exists()
    assert (tmp_path / "data" / "rds.db").exists()


def test_manifest_round_trips_through_read_manifest(tmp_path):
    # The written Provisioning manifest round-trips via read_manifest.
    store, _row_d1, _row_d2 = _store(tmp_path)
    hash_set, record = _provision(
            tmp_path, [_DELTA_1, _DELTA_2], store=store)
    manifest_path = tmp_path / "data" / "manifest.json"
    assert read_manifest(manifest_path) == record
    assert verify_readiness(read_manifest(manifest_path), hash_set) is True


def test_verify_reports_ready_volume(tmp_path):
    # make verify re-checks the provisioned volume and reports ready.
    store, _row_d1, _row_d2 = _store(tmp_path)
    _provision(tmp_path, [_DELTA_1], store=store)
    result = verify_release(str(tmp_path / "data"))
    assert result.ready is True
    assert result.checks["manifest"] == "present"
    assert result.checks["well_formed"] is True
    assert result.checks["ready"] is True


def test_verify_refuses_missing_manifest(tmp_path):
    # make verify on an unprovisioned volume is not-ready.
    data = tmp_path / "data"
    data.mkdir()
    result = verify_release(str(data))
    assert result.ready is False
    assert result.checks["manifest"] == "absent"


def test_verify_refuses_missing_hash_set(tmp_path):
    # A manifest whose mounted Hash Set is gone is a stale, not-ready volume.
    store, _row_d1, _row_d2 = _store(tmp_path)
    _provision(tmp_path, [_DELTA_1], store=store)
    (tmp_path / "data" / "rds.db").unlink()
    result = verify_release(str(tmp_path / "data"))
    assert result.ready is False
    assert result.checks["hash_set"] == "absent"


def test_tampered_layer_refuses_manifest_write(tmp_path):
    # A zip whose SHA-1 sidecar fails (layer 1) refuses the manifest write.
    store, _row_d1, _row_d2 = _store(tmp_path)
    rzip = "RDS_" + _RELEASE + "_modern_minimal.zip"
    store[_BASE + "/rds_" + _RELEASE + "/" + rzip + ".sha"] = (
             _sha1_sidecar(rzip, "0" * 40))
    try:
         _provision(tmp_path, [_DELTA_1], store=store)
    except IntegrityError:
        pass
    else:
        raise AssertionError("expected a tampered layer to be refused")
    assert not (tmp_path / "data" / "manifest.json").exists()


def test_missing_published_token_refuses(tmp_path):
    # A dbhashes.txt missing the Release's token refuses the manifest write.
    store, _row_d1, _row_d2 = _store(tmp_path)
    store[_BASE + "/rds_" + _RELEASE + "/dbhashes.txt"] = (
            b"052bcc RDS_2026.09.1_legacy.db\n")
    try:
         _provision(tmp_path, [], store=store)
    except IntegrityError:
        pass
    else:
        raise AssertionError("expected a missing token to be refused")
    assert not (tmp_path / "data" / "manifest.json").exists()


def test_reapply_is_a_noop_for_ordered_list(tmp_path):
    # A delta already recorded is a no-op for the ordered list on re-apply.
    store, row_d1, _row_d2 = _store(tmp_path)
    _hash_set, _record = _provision(tmp_path, [_DELTA_1], store=store)
    set_obj = hasheset.provision(
            str(tmp_path / "data" / "rds.db"),
             hasheset.Provenance("modern", _RELEASE, [_DELTA_1], _DBHASH))
    sql_text = build_delta_sql([row_d1])
    redone = apply_delta_releases(set_obj, [(_DELTA_1, sql_text)])
    assert list(redone.provenance.deltas) == [_DELTA_1]


def test_scratch_unlink_never_touches_paths_outside_roots(tmp_path):
    # A database outside the scratch roots survives; one inside is removed.
    work = tmp_path / "work"
    work.mkdir()
    inside = work / "stale.db"
    inside.write_bytes(b"scratch")
    outside = tmp_path / "keep.db"
    outside.write_bytes(b"not scratch")
    _remove_if_scratch(inside, (work,))
    assert not inside.exists()
    _remove_if_scratch(outside, (work,))
    assert outside.exists()


def test_scratch_unlink_tolerates_a_missing_path(tmp_path):
    # A path already gone (renamed to its final place) is a no-op, not an
    # error (ADR-0007): hygiene must not raise on a superseded rename.
    work = tmp_path / "work"
    work.mkdir()
    _remove_if_scratch(work / "gone.db", (work,))


def test_find_skips_metadata_twins(tmp_path):
    # A `._<name>` AppleDouble twin also *ends with* the base name; it must
    # never be served where the real file is expected (ADR-0007 run 1 died
    # applying one as if it were the delta script).
    inner = tmp_path / "tree"
    inner.mkdir()
    real = inner / "RDS_x_modern_minimal_delta.sql"
    real.write_bytes(b"BEGIN TRANSACTION;\nCOMMIT;\n")
    (inner / "._RDS_x_modern_minimal_delta.sql").write_bytes(
        b"\x00\x05\x16\x07._Icon")
    assert _find(inner, "RDS_x_modern_minimal_delta.sql") == real
    (inner / "RDS_y.db").write_bytes(b"real db")
    (inner / "._RDS_y.db").write_bytes(b"twin")
    assert _find(inner, ".db") == inner / "RDS_y.db"


def test_extract_rebuilds_a_stale_tree(tmp_path):
    # Extracts land in a long-lived scratch dir: files left by a previous,
    # crashed run must not survive into the new tree.
    dest = tmp_path / "extracted" / "RDS_x_modern_minimal"
    dest.mkdir(parents=True)
    (dest / "stale_from_crashed_run.sql").write_bytes(b"junk")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("RDS_x_modern_minimal/readme.txt", b"hello")
    zip_path = tmp_path / "RDS_x_modern_minimal.zip"
    zip_path.write_bytes(buffer.getvalue())
    tree = _extract(zip_path, dest)
    assert not (tree / "stale_from_crashed_run.sql").exists()
    assert (tree / "RDS_x_modern_minimal" / "readme.txt").read_bytes(
    ) == b"hello"


def test_move_or_copy_renames_on_one_volume(tmp_path):
    # Same volume: O(1) rename, source gone, content intact (ADR-0007).
    src = tmp_path / "in" / "base.db"
    src.parent.mkdir()
    src.write_bytes(b"payload")
    out = tmp_path / "data" / "rds.db"
    out.parent.mkdir()
    _move_or_copy(src, out)
    assert not src.exists()
    assert out.read_bytes() == b"payload"


def test_move_or_copy_copies_across_volumes(tmp_path, monkeypatch):
    # Across volumes: streamed copy; the scratch source stays for hygiene.
    src = tmp_path / "in" / "base.db"
    src.parent.mkdir()
    src.write_bytes(b"payload")
    out = tmp_path / "data" / "rds.db"
    out.parent.mkdir()
    import os
    from types import SimpleNamespace
    real_stat = os.stat
    def fake_stat(path, *, dir_fd=None, follow_symlinks=True):
        # Only the two directory parents are cross-volume in this fake;
        # everything else stats for real via the captured function.
        name = Path(path).name
        if name in ("in", "data"):
            return SimpleNamespace(
                st_dev=1 if name == "in" else 2)
        return real_stat(
            path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
    monkeypatch.setattr("driver.os.stat", fake_stat)
    _move_or_copy(src, out)
    assert out.read_bytes() == b"payload"
    assert src.read_bytes() == b"payload"


def test_turnkey_applies_deltas_in_place_without_tmp_copies(tmp_path,
                                                             monkeypatch):
    # The run's working copy is scratch, so Deltas apply in place and the
    # finished database is renamed into the data dir: no second, third, or
    # fourth full database ever exists (ADR-0007).
    store, _row_d1, _row_d2 = _store(tmp_path)
    tmp_root = tmp_path / "scratch_tmp"
    tmp_root.mkdir()
    real_mkstemp = tempfile.mkstemp
    calls = []

    def fake_mkstemp(suffix=".db"):
        calls.append(suffix)
        return real_mkstemp(suffix=suffix, dir=str(tmp_root))

    monkeypatch.setattr(
        "hasheset.tempfile.mkstemp", fake_mkstemp)
    _provision(tmp_path, [_DELTA_1, _DELTA_2], store=store)
    assert calls == []
    assert list(tmp_root.glob("*.db")) == []
    assert not (tmp_path / "work" / "base.db").exists()
    assert (tmp_path / "data" / "rds.db").exists()
    # Both deltas' rows ride on the renamed volume.
    result = verify_release(str(tmp_path / "data"))
    assert result.ready is True


def test_apply_copies_when_base_outside_scratch(tmp_path, monkeypatch):
    # A database outside the scratch roots -- a trusted mounted volume -- is
    # protected by copy-on-apply: the source is untouched, the copy lands in
    # system scratch (ADR-0005/ADR-0007).
    store, _row_d1, _row_d2 = _store(tmp_path)
    _provision(tmp_path, [_DELTA_1], store=store)
    set_obj = hasheset.provision(
        str(tmp_path / "data" / "rds.db"),
        hasheset.Provenance("modern", _RELEASE, [_DELTA_1], _DBHASH))
    tmp_root = tmp_path / "scratch_tmp"
    tmp_root.mkdir()
    real_mkstemp = tempfile.mkstemp

    def fake_mkstemp(suffix=".db"):
        return real_mkstemp(suffix=suffix, dir=str(tmp_root))

    monkeypatch.setattr(
        "hasheset.tempfile.mkstemp", fake_mkstemp)
    row = _row("CCCC5C5C5C5C5C5C5C5C5C5C5C5C5C5C5C", "delta3.bin")
    redone = apply_delta_releases(
        set_obj, [(_DELTA_2, build_delta_sql([row]))],
        scratch_dirs=(tmp_path / "work",))
    assert len(list(tmp_root.glob("*.db"))) == 1
    assert redone.is_known(
        "md5", "CCCC5C5C5C5C5C5C5C5C5C5C5C5C5C5C5C")
    # The volume never absorbed the delta.
    assert not set_obj.is_known(
        "md5", "CCCC5C5C5C5C5C5C5C5C5C5C5C5C5C5C5C")


def test_hygiene_removes_tmp_intermediates(tmp_path, monkeypatch):
    # Copy-on-apply scratch dbs are removed as the run progresses.
    store, _row_d1, _row_d2 = _store(tmp_path)
    tmp_root = tmp_path / "scratch_tmp"
    tmp_root.mkdir()
    real_mkstemp = tempfile.mkstemp

    def fake_mkstemp(suffix=".db"):
        return real_mkstemp(suffix=suffix, dir=str(tmp_root))

    monkeypatch.setattr("hasheset.tempfile.mkstemp", fake_mkstemp)
    _provision(tmp_path, [_DELTA_1, _DELTA_2], store=store)
    assert list(tmp_root.glob("*.db")) == []
    assert not (tmp_path / "work" / "base.db").exists()
    assert (tmp_path / "data" / "rds.db").exists()
