"""The turnkey Provisioner driver: one command to a verified ``ready`` state.

This is the thin orchestration the **Provisioner** (Seam 3, I/O-bound) ties
together end to end: ``make provision`` fetches the full Minimal **Release**
and its ordered **Delta releases** from NIST (ticket 02's ``fetch_set``),
verifies the archive in three layers -- the zip **SHA-1** against each
``.sha`` sidecar, the inner files' **SHA-256** against each zip's inner
``signatures.txt``, and NIST's published **``dbhash``** read from the
terminal release's ``dbhashes.txt`` (record-and-attest, ticket 01) -- then
applies the deltas in
order, records the published token, and writes the queryable **Hash Set** (with
its per-Algorithm **hash index** built into the same database) + the
**Provisioning manifest** into the data dir. ``make
verify`` re-checks an already-provisioned volume.

A layer failure *refuses* the manifest write (ADR-0005): an unverified or
partially-applied **Hash Set** can never be served, so every integrity check
runs before the manifest is written. The **API boundary (Seam 1)** and the
**lookup module (Seam 2)** are untouched. The heavy multi-gigabyte download is
the operator's step and is never a build or CI step (ADR-0003); the driver
orchestrates, the human runs it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import hasheset
import provision
from hasheset import Provenance
from provision import _DEFAULT_FAMILY
from provision import _NIST_BASE

_DB_NAME = "rds.db"
MANIFEST_NAME = "manifest.json"


class IntegrityError(RuntimeError):
    """The archive failed an integrity layer; the manifest is not written."""


@dataclass
class VolumeResult:
    """The outcome of a ``make verify`` re-check of a provisioned volume."""

    ready: bool
    checks: dict


def final_db_name(release, family=_DEFAULT_FAMILY):
    """The final post-delta database object NIST publishes a ``dbhash`` for."""
    return "RDS_" + release + "_" + family + ".db"


def release_from_zip(name, family=_DEFAULT_FAMILY):
    """Derive the **Release** id from a full-Minimal Release zip name."""
    prefix = "RDS_"
    suffix = "_" + family + ".zip"
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix):-len(suffix)]
    raise IntegrityError("cannot derive release from " + name)


def delta_sql_name(delta_release, family=_DEFAULT_FAMILY):
    """The ordered Delta's SQLite script, inside its delta release zip."""
    return "RDS_" + delta_release + "_" + family + "_delta.sql"


def _find(inner_dir, suffix):
    """Walk an extracted archive tree, returning the first file by suffix."""
    for root, _, files in os.walk(inner_dir):
        for name in files:
            if name.endswith(suffix):
                return Path(root) / name
    return None


def _extract(archive, dest_dir):
    """Unzip an NIST archive, flat over its top folder so inner files match."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zip_file:
        for name in zip_file.namelist():
            if not name.endswith("/"):
                zip_file.extract(name, dest)
    return dest


def _bases(fetched):
    """The full **Release** zip then every ordered **Delta release** zip."""
    pairs = [(fetched.release_zip, fetched.release_sidecar)]
    for delta in fetched.deltas:
        pairs.append((delta.zip, delta.sidecar))
    return pairs


def _verify_layers(fetched, work_dir, family=_DEFAULT_FAMILY):
    """Run all three integrity layers, refusing on the first failure.

    Each layer is checked across the full **Release** zip and every ordered
    **Delta release** zip -- before any manifest write -- so a tampered,
    missing, or unattested artifact is caught and the **Hash Set** is never
    produced (ADR-0005). Layer 1 is the zip **SHA-1** vs its sidecar; layer 2
    is the inner files' **SHA-256** vs each zip's inner ``signatures.txt``;
    layer 3 is NIST's published **``dbhash``** read from the terminal
    release's ``dbhashes.txt`` -- for the final post-Delta database, since
    only the terminal release's file carries that token -- and recorded, not
    recomputed (ADR-0006).
    """
    release = release_from_zip(fetched.release_zip.name, family)
    terminal = provision.terminal_release(
        release, [delta.release for delta in fetched.deltas])
    inner = {}
    for zip_path, sidecar in _bases(fetched):
        if not provision.verify_zip_sha(zip_path, sidecar):
            raise IntegrityError("layer 1 failed for " + str(zip_path))
        extracted = _extract(zip_path, Path(work_dir) / "extracted" /
                             zip_path.stem)
        signatures = _find(extracted, "signatures.txt")
        if signatures is None or not provision.verify_signatures(
                signatures.parent, signatures):
            raise IntegrityError("layer 2 failed for " + str(zip_path.name))
        inner[zip_path.name] = extracted
    token = provision.read_published_dbhash(
        fetched.dbhashes, final_db_name(terminal, family))
    return token, inner


def _inside_resolved(path, root):
    """True iff `path` resolves to a file inside `root` (ADR-0005 scoping)."""
    try:
        resolved = Path(path).resolve()
    except OSError:
        return False
    if not resolved.is_file():
        return False
    try:
        resolved.relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True


def _remove_if_scratch(path, scratch_dirs):
    """Remove a scratch database only if it sits inside a scratch root.

    The turnkey run's intermediates -- the per-apply copy-on-apply database
    and the base's working copy -- are deleted as they are superseded, so the
    run leaves no multi-hundred-GiB scratch trail (ADR-0003). The unlink is
    resolved and scoped: anything outside the given roots (a mounted volume,
    the data dir) is never touched (ADR-0005).
    """
    for root in scratch_dirs:
        if _inside_resolved(path, root):
            Path(path).unlink()
            return


def _scratch_dirs(work_dir):
    """The run's scratch roots: its work dir and the system temp dir.

    ``apply_delta``'s copy-on-apply copies land in the system temp dir
    (``tempfile.mkstemp``), the base working copy in the work dir; both are
    disposable scratch, never the data volume.
    """
    return (Path(work_dir), Path(tempfile.gettempdir()))


def apply_delta_releases(base, ordered, scratch_dirs=()):
    """Apply the ordered **Delta releases** onto the base Set, in order.

     Each Delta is a NIST-ordered ``.sql`` script, applied by copy-on-apply + a
    streaming ``execute`` (ticket 04), refreshing the per-Algorithm
    **hash index** and provenance. A Delta is streamed from its on-disk path,
    never whole; one already in the base's provenance is a no-op for the ordered
    list (``apply_delta`` dedupes), so a re-run never duplicates it.
    Scratch hygiene: when `scratch_dirs` is given, each superseded database is
    removed after its successor is produced, iff it resolves inside one of the
    roots (ADR-0003/ADR-0005).
     """
    current = base
    for release_name, delta_sql in ordered:
        superseded = current
        current = hasheset.apply_delta(current, delta_sql, release_name)
        _remove_if_scratch(superseded.path, scratch_dirs)
    return current


def provision_release(release, deltas, *,
                      data_dir, work_dir,
                      set_name="modern", family=_DEFAULT_FAMILY,
                      base=None,
                      opener=urllib.request.urlopen):
    """The turnkey flow, end to end, writing the volume into the data dir.

     Fetch, verify all three layers, apply the deltas in order, record NIST's
    published ``dbhash``, and write the queryable **Hash Set**, its per-
    Algorithm **hash index**, built into the same database, plus the
    **Provisioning manifest**. Returns the provisioned Set and the written
    manifest record.

    The multi-gigabyte **Release** fetch is the operator's step (ADR-0003);
    ``opener`` is injected so the wiring is assertable without it. Any
    integrity-layer failure raises before the manifest write, so an unverified
    or partially-applied **Hash Set** is never produced (ADR-0005). The final
    **``dbhash``** is NIST's published value, recorded (attested), not
    recomputed (ADR-0006).

    Scratch hygiene keeps the run from peaking at triple the final volume:
    the base's extracted tree is removed once its database has been copied to
    the work dir, each superseded copy-on-apply database is removed once its
    successor exists, and the final applied database is removed once copied
    into the data dir -- in every case only when the path resolves inside the
    run's work dir or the system temp dir, never the data volume (ADR-0005).
    """
    base_url = base if base is not None else _NIST_BASE
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    data = Path(data_dir)
    data.mkdir(parents=True, exist_ok=True)

    fetched = provision.fetch_set(
        release, deltas, work, base=base_url, family=family, opener=opener)

    terminal = provision.terminal_release(
        release, [delta.release for delta in fetched.deltas])
    token, inner = _verify_layers(fetched, work_dir, family=family)
    if token is None:
        raise IntegrityError(
            "no published dbhash for " + final_db_name(terminal, family)
            + " in dbhashes.txt")

    base_db = _find(inner[fetched.release_zip.name], ".db")
    if base_db is None:
        raise IntegrityError("release zip has no base .db for " + release)
    base_path = work / "base.db"
    shutil.copyfile(base_db, base_path)
    shutil.rmtree(base_db.parent, ignore_errors=True)
    base_set = hasheset.provision(base_path, Provenance(set_name, release))

    ordered = []
    for delta in fetched.deltas:
        sql = _find(inner[delta.zip.name],
                    delta_sql_name(delta.release, family))
        if sql is None:
            raise IntegrityError(
                "delta release " + delta.release + " has no .sql script")
        ordered.append((delta.release, sql))
    scratch = _scratch_dirs(work)
    applied = apply_delta_releases(base_set, ordered, scratch)

    target = data / _DB_NAME
    shutil.copyfile(applied.path, target)
    _remove_if_scratch(applied.path, scratch)
    record = provision.write_manifest(
        data / MANIFEST_NAME, set_name, release,
        applied.provenance.deltas, token)
    hash_set = hasheset.provision(
        target, Provenance(set_name, release, applied.provenance.deltas,
                           token))
    return hash_set, record


def verify_release(data_dir):
    """``make verify``: re-check an already-provisioned volume.

    The volume is trusted only when its **Provisioning manifest** is present and
    well-formed and the mounted **Hash Set** agrees with it
    (``verify_readiness``); a missing or mismatched manifest is not-ready, so a
    stale volume answers nothing (ADR-0005).
    """
    data = Path(data_dir)
    result = {"manifest": "absent"}
    manifest_path = data / MANIFEST_NAME
    if not manifest_path.exists():
        return VolumeResult(ready=False, checks=result)
    manifest = provision.read_manifest(manifest_path)
    result["manifest"] = "present"
    missing = [key for key in
               ("set", "release", "deltas", "dbhash")
               if key not in manifest]
    result["well_formed"] = not missing
    if missing:
        return VolumeResult(ready=False, checks=result)
    db_path = data / _DB_NAME
    result["hash_set"] = "present" if db_path.exists() else "absent"
    if not db_path.exists():
        return VolumeResult(ready=False, checks=result)
    hash_set = hasheset.HashSet(
        db_path,
        Provenance(manifest["set"], manifest["release"],
                   tuple(manifest.get("deltas") or ()), manifest["dbhash"]))
    ready = hasheset.verify_readiness(manifest, hash_set)
    result["ready"] = ready
    return VolumeResult(ready=ready, checks=result)


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Turnkey Provisioner driver")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("provision", help="Provision a fresh data dir")
    make.add_argument("--release", required=True)
    make.add_argument("--deltas", nargs="*", default=[])
    make.add_argument("--data-dir", default="/data")
    make.add_argument("--work-dir", default="/tmp/nsrl_provision")
    make.add_argument("--set-name", default="modern")
    make.add_argument("--family", default=_DEFAULT_FAMILY)
    check = sub.add_parser("verify", help="Re-check a provisioned volume")
    check.add_argument("--data-dir", default="/data")
    return parser.parse_args(argv)


def main(argv=None):
    """The CLI entry the ``Makefile`` wires to provision / verify."""
    args = _parse_args(argv)
    if args.command == "provision":
        _, record = provision_release(
            args.release, list(args.deltas), data_dir=args.data_dir,
            work_dir=args.work_dir, set_name=args.set_name,
            family=args.family)
        print("provisioned " + str(record))
        return 0
    result = verify_release(args.data_dir)
    print(str(result.checks))
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
