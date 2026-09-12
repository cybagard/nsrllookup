"""The Provisioner: a one-time, out-of-band flow that produces a queryable
Hash Set (Seam 3, I/O-bound; never a build or CI step).

It verifies a released archive in three layers -- the zip's SHA-1 against its
sidecar, the inner files' SHA-256 against signatures.txt, and NIST's dbhash
over the final post-delta database against dbhashes.txt -- then applies the
ordered Deltas and writes the Hash Set's Sidecar index and Provisioning
manifest. The dbhash layer is an external token function (ADR-0006): NIST's
binary is accepted rather than re-implemented, and is injected so it is
assertable without the binary present.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import hasheset
from hasheset import Provenance

_SIDECAR = re.compile(
        r"^SHA1\((?P<name>[^)]+)\)\s*=\s*(?P<digest>[0-9a-fA-F]+)\s*$")

_SIGNATURE = re.compile(
        r"^SHA256\((?P<name>[^)]+)\)\s*=\s*(?P<digest>[0-9a-fA-F]+)\s*$")


def verify_zip_sha(zip_path: Path, sidecar: Path) -> bool:
    # Layer 1: the zip's SHA-1 matches its sidecar (NIST's `SHA1` file).
    expected = _expected_line(sidecar)
    if expected is None:
        return False
    return hashlib.sha1(zip_path.read_bytes()).hexdigest() == expected.lower()


def verify_signatures(signed_dir: Path, signatures: Path) -> bool:
    # Layer 2: each inner file's SHA-256 matches NIST's signatures.txt.
    for raw in signatures.read_text(encoding="utf-8").splitlines():
        match = _SIGNATURE.match(raw.strip())
        if match is None:
            continue
        name, expected = match.group("name"), match.group("digest")
        if not (signed_dir / name).exists():
            return False
        actual = hashlib.sha256((signed_dir / name).read_bytes()).hexdigest()
        if actual != expected.lower():
            return False
    return True


def verify_dbhash(db_path, published, dbhash):
    # Layer 3: the dataset token equals the published dbhashes.txt value.
    return dbhash(db_path) == published.lower()


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
