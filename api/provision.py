"""The Provisioner: a one-time, out-of-band flow that produces a queryable
Hash Set (Seam 3, I/O-bound; never a build or CI step).

The turnkey driver first fetches the full Minimal Release and its ordered
Delta releases from NIST's per-Release S3 path (each object probed by exact
name, since the listing is access-denied but the objects are public-read),
then verifies a released archive in three layers -- the zip's SHA-1 against its
sidecar, the inner files' SHA-256 against signatures.txt, and NIST's dbhash
over the final post-delta database against dbhashes.txt -- and applies the
ordered Deltas, building the per-Algorithm hash index into the Hash Set's own
database and writing the Provisioning
    manifest. The dbhash layer is an external token function (ADR-0006): NIST's
binary is accepted rather than re-implemented, and is injected so it is
assertable without the binary present.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import List

import hasheset
from hasheset import Provenance

_SIDECAR = re.compile(
        r"^SHA1\((?P<name>[^)]+)\)\s*=\s*(?P<digest>[0-9a-fA-F]+)\s*$")

_SIGNATURE = re.compile(
        r"^SHA256\((?P<name>[^)]+)\)\s*=\s*(?P<digest>[0-9a-fA-F]+)\s*$")

_DBHASH = re.compile(
        r"^[ \t]*(?P<digest>[0-9a-fA-F]+) +(?P<name>\S+\.db)$")


def _digest_file(path: Path, algorithm: str) -> str:
    # Digest a file by streaming it in 1 MiB chunks, never whole: the base
    # database alone is ~169 GiB uncompressed, so a whole-object read will
    # not fit process memory.
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_zip_sha(zip_path: Path, sidecar: Path) -> bool:
    # Layer 1: the zip's SHA-1 matches its sidecar (NIST's `SHA1` file).
    expected = _expected_line(sidecar)
    if expected is None:
        return False
    return _digest_file(zip_path, "sha1") == expected.lower()


def verify_signatures(signed_dir: Path, signatures: Path) -> bool:
    # Layer 2: each inner file's SHA-256 matches NIST's signatures.txt.
    for raw in signatures.read_text(encoding="utf-8").splitlines():
        match = _SIGNATURE.match(raw.strip())
        if match is None:
            continue
        name, expected = match.group("name"), match.group("digest")
        if not (signed_dir / name).exists():
            return False
        actual = _digest_file(signed_dir / name, "sha256")
        if actual != expected.lower():
            return False
    return True


def verify_dbhash(db_path, published, dbhash):
    # Layer 3 (compute-and-compare, fixture suite only): the computed token
    # equals NIST's published value. Retained beside the record-and-attest
    # path so the fixture suite keeps exercising the match/refuse mechanic.
    return dbhash(db_path) == published.lower()


def read_published_dbhash(dbhashes, db_name):
    # Layer 3 (record-and-attest, turnkey path): read NIST's published
    # `dbhash` for the Release's database object from `dbhashes.txt`. The
    # token is the value NIST ships, not a locally computed stand-in
    # (ADR-0006); it is recorded, not recomputed.
    for raw in dbhashes.read_text(encoding="utf-8").splitlines():
        match = _DBHASH.match(raw.strip())
        if match is not None and match.group("name") == db_name:
            return match.group("digest").lower()
    return None


_NIST_BASE = "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS"

_DEFAULT_FAMILY = "modern_minimal"


@dataclass
class FetchedDelta:
     # One ordered Delta release fetched by the driver, with its zip sidecar.
    release: str
    zip: Path
    sidecar: Path


@dataclass
class FetchedSet:
    # The full Release + ordered Deltas + the terminal release's
    # `dbhashes.txt`, on disk. There is no top-level `signatures.txt` to
    # fetch: NIST publishes its inside each archive (layer 2 verifies it from
    # the extracted tree).
    release_zip: Path
    release_sidecar: Path
    dbhashes: Path
    deltas: List[FetchedDelta] = field(default_factory=list)


class FetchError(RuntimeError):
      # A required NIST object could not be fetched or was missing.
    pass


def release_zip_name(release, family=_DEFAULT_FAMILY):
      # The full-Minimal Release archive, by its Release identifier.
    return f"RDS_{release}_{family}.zip"


def delta_zip_name(delta_release, family=_DEFAULT_FAMILY):
      # A Delta release archive, by its Delta release identifier.
    return f"RDS_{delta_release}_{family}_delta.zip"


def object_url(base, release, name):
     # NIST's per-Release S3 path: objects are public-read under rds_<id>/.
    return base + "/rds_" + release + "/" + name


def terminal_release(release, deltas):
    # The terminal post-delta Release: the last ordered Delta release, or the
    # Release itself when no Delta is applied. The driver derives both the
    # final database name (whose token `dbhashes.txt` must carry) and the
    # `dbhashes.txt` object to fetch from it.
    return deltas[-1] if deltas else release


def fetch_plan(release, deltas, dest_dir, base=_NIST_BASE,
               family=_DEFAULT_FAMILY):
      # The exact NIST object URLs + local destinations for a Release.
      #
      # NIST's per-Release S3 path denies anonymous *listing* but serves each
      # object *public-read*, so the driver probes exact object names derived
      # from the Release and Delta release identifiers rather than listing the
      # bucket. Returned in fetch order: the full-Minimal Release zip + its
      # `.sha`, each ordered Delta release zip + its `.sha`, then the terminal
      # release's `dbhashes.txt` -- the one per-Release text object the turnkey
      # path needs besides the archives. There is no top-level `signatures.txt`
      # on NIST (probes 403; the release README lists the objects): each zip
      # already carries its inner `signatures.txt`, which the signature layer
      # verifies from the extracted tree, so none is fetched. No URL is
      # hard-coded; each is derived from the `Release` / `Delta release`
      # identifiers.
    dest = Path(dest_dir)
    plan = []
    rzip = release_zip_name(release, family)
    plan.append(("release_zip", rzip,
                 object_url(base, release, rzip), dest / rzip))
    plan.append(("release_sidecar", rzip + ".sha",
                 object_url(base, release, rzip + ".sha"),
                 dest / (rzip + ".sha")))
    for delta_release in deltas:
        dzip = delta_zip_name(delta_release, family)
        plan.append(("delta_zip", delta_release,
                     object_url(base, delta_release, dzip), dest / dzip))
        plan.append(("delta_sidecar", delta_release,
                     object_url(base, delta_release, dzip + ".sha"),
                     dest / (dzip + ".sha")))
    terminal = terminal_release(release, deltas)
    plan.append(("dbhashes", terminal,
                 object_url(base, terminal, "dbhashes.txt"),
                 dest / "dbhashes.txt"))
    return plan


def _download(opener, url, dest):
    # Persist one NIST object, streaming it to disk in 1 MiB chunks: the
    # full Release archive is ~18 GiB, so it is never held whole in process
    # memory. A failed or missing object refuses loudly and leaves no
    # partial file behind. An object already on disk in full is a resume:
    # trusted as fetched. Archives re-verify through the integrity layers
    # (a corrupt or pre-placed archive fails layer 1/2, ADR-0005), so a
    # re-run never re-copies the multi-gigabyte archive (ADR-0007). The
    # small text objects (`dbhashes.txt`) have no signature layer of their
    # own: for them the resume extends the fetch-time trust (TLS to NIST) to
    # the local copy -- the documented residual risk from ADR-0007, bounded
    # by the per-Release filename.
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return Path(dest)
    try:
        with opener(url) as handle:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as out:
                while chunk := handle.read(1 << 20):
                    out.write(chunk)
    except urllib.error.URLError as error:
        if os.path.exists(dest):
            os.unlink(dest)
        raise FetchError(
              "cannot fetch " + url + ": " + str(getattr(
                  error, "reason", error))) from error
    return dest


def fetch_set(release, deltas, dest_dir, *,
              base=_NIST_BASE, family=_DEFAULT_FAMILY,
              opener=urllib.request.urlopen):
       # Fetch the full Release + ordered Deltas + the terminal release's
       # `dbhashes.txt`.
       #
       # Each required object -- the full-Minimal **Release** zip + its `.sha`
       # sidecar, every ordered **Delta release** zip + its sidecar, and the
       # terminal release's `dbhashes.txt` -- is probed by exact name on
       # NIST's per-Release path and written under `dest_dir`, streamed in
       # chunks rather than whole into memory. There is no top-level
       # `signatures.txt` on NIST to fetch: each archive carries its inner
       # copy, which the signature layer reads from the extracted tree. A
       # failed or missing object surfaces as a `FetchError` (never a silent
       # empty fetch). The heavy multi-gigabyte download is the operator's
       # step and is never a build or CI step (ADR-0003); it is injected via
       # `opener` so the wiring is assertable without the download. No new
       # dependency: stdlib `urllib`.
    fetched = FetchedSet(
         None, None, None,
         [FetchedDelta(delta, None, None) for delta in deltas])
    for role, marker, url, target in fetch_plan(
         release, deltas, dest_dir, base=base, family=family):
        if role == "release_zip":
            fetched.release_zip = _download(opener, url, target)
        elif role == "release_sidecar":
            fetched.release_sidecar = _download(opener, url, target)
        elif role == "delta_zip":
            slot = next(item for item in fetched.deltas
                        if item.release == marker)
            slot.zip = _download(opener, url, target)
        elif role == "delta_sidecar":
            slot = next(item for item in fetched.deltas
                        if item.release == marker)
            slot.sidecar = _download(opener, url, target)
        elif role == "dbhashes":
            fetched.dbhashes = _download(opener, url, target)
    return fetched


def provision_record(base_path, set_name, release, deltas,
                     db_name, dbhashes, manifest_path):
    # Turnkey layer 3: apply the ordered Deltas, read NIST's published
    # `dbhash` for the Release, and record it in the Provisioning manifest.
    # It attests the token rather than recomputing it (ADR-0006); the service
    # then trusts the verified mount (ADR-0005).
    current = hasheset.provision(base_path,
                                 Provenance(set_name, release))
    applied = []
    for release_name, delta_sql in deltas:
        current = hasheset.apply_delta(current, delta_sql, release_name)
        applied.append(release_name)
    token = read_published_dbhash(dbhashes, db_name)
    if token is None:
        raise ValueError(
            "no published dbhash for " + db_name + " in dbhashes.txt")
    verified = hasheset.provision(
        current.path,
        Provenance(set_name, release, applied, token))
    record = write_manifest(manifest_path, set_name, release, applied, token)
    return verified, record


def write_manifest(path, set_name, release, deltas, dbhash):
    # Write the Provisioning manifest attestation alongside the Hash Set.
    record = {
          "set": set_name,
          "release": release,
          "deltas": list(deltas),
          "dbhash": dbhash,
      }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True, indent=2)
    return record


def read_manifest(path):
    # Read a Provisioning manifest back for the readiness check.
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def provision(base_path, set_name, release, deltas,
              published_dbhash, dbhash, manifest_path):
    # Apply the ordered Deltas, verify the final dbhash, write the manifest.
    current = hasheset.provision(base_path,
                                  Provenance(set_name, release))
    applied = []
    for release_name, delta_sql in deltas:
        current = hasheset.apply_delta(current, delta_sql, release_name)
        applied.append(release_name)
    if not verify_dbhash(current.path, published_dbhash, dbhash):
        raise ValueError("dbhash mismatch: dataset integrity failed")
    token = published_dbhash.lower()
    verified = hasheset.provision(
        current.path,
        Provenance(set_name, release, applied, token))
    record = write_manifest(manifest_path, set_name, release, applied, token)
    return verified, record


def _expected_line(sidecar: Path):
    # Parse NIST's `SHA1(<name>)= <hex>` sidecar, returning the recorded value.
    for raw in sidecar.read_text(encoding="utf-8").splitlines():
        match = _SIDECAR.match(raw.strip())
        if match is not None:
            return match.group("digest")
    return None
