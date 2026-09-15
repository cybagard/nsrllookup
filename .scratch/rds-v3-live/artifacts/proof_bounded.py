"""Bounded real-data proof of the turnkey path (prod-functional ticket 04).

The full-volume apply -- the ~18 GiB Minimal Release extracted to a ~169 GiB
base with both Deltas applied -- is the operator's out-of-CI step (ADR-0003).
This proof exercises the real code path on real NIST artifacts without that
volume, so it never reproduces the 169 GiB base and stays safe on a tight disk:

 * Layer 1 (transport): streamed zip SHA-1 over the real 18 GiB release zip,
   matched to NIST's .sha sidecar.
 * Layer 2 (contents): real inner SHA-256 over a real extracted Delta .sql,
   matched to the zip's inner signatures.txt via provision.verify_signatures.
 * Layer 3 (dataset dbhash): the real NIST token read from the real dbhashes.txt
   for the terminal Release's final db (481e5f55...), recorded not recomputed
   (ADR-0006).
   * Turnkey apply: a capped prefix of the real Delta .sql is applied, one
    Delta at a time, by the production hasheset.apply_delta (streamed,
    line-batched -- the same applier the driver uses), onto a small base seeded
    from real delta rows, proving the large-delta apply neither OOMs nor blows
    up disk. A digest the apply inserted is Known; an unrelated digest is
    Unknown.
 * Boot: verify_readiness confirms the volume, and a service boot answers /check
   carrying the real token in its dataset block.

Peak RSS is reported, then the working dirs are removed.
"""

import hashlib
import os
import re
import resource
import shutil
import sqlite3
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
RAW = HERE / "raw"
ROOT = HERE / ".." / ".." / ".."
sys.path.insert(0, str(ROOT / "api"))

import app   # noqa: E402
import boot   # noqa: E402
import hasheset   # noqa: E402
import provision   # noqa: E402

NIST_BASE = "https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS"
RELEASE = "2026.03.1"
DELTAS = ["2026.06.1", "2026.09.1"]
TERMINAL = "2026.09.1"
FAMILY = "modern_minimal"
PUBLISHED_TOKEN = "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
FINAL_DB = "RDS_2026.09.1_modern_minimal.db"
CAP = 40_000

# (release, object name) for each artifact whose transport integrity layer 1
# attests. NIST publishes a full Minimal base once per cycle (03.1) and delta
# archives for the subsequent quarters (06.1, 09.1): the full 09.1 zip does not
# exist (HTTP 403), so 09.1 is a delta.
ARTIFACTS = [
    (RELEASE, f"RDS_{RELEASE}_{FAMILY}.zip"),
    ("2026.06.1", f"RDS_{DELTAS[0]}_{FAMILY}_delta.zip"),
    ("2026.09.1", f"RDS_{DELTAS[1]}_{FAMILY}_delta.zip"),
]

CHECKS = []
SIDECAR = re.compile(
    r"^SHA1\((?P<name>[^)]+)\)\s*=\s*(?P<digest>[0-9a-fA-F]+)\s*$")


def check(label, ok, detail=""):
    CHECKS.append((bool(ok), label))
    print(("PASS " if ok else "FAIL ") + label
           + ((" -- " + detail) if detail else ""))


def peak_rss_mib():
     # macOS reports ru_maxrss in bytes.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def sha1_stream(path, chunk=1024 * 1024):
     # Layer 1 mechanic: streamed SHA-1, chunked, so the 18 GiB zip never loads
     # whole (no OOM).
    h = hashlib.sha1()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sidecar_digest(sidecar_path):
     # Parse NIST's SHA1(name)= <hex> sidecar.
    for raw in sidecar_path.read_text(encoding="utf-8").splitlines():
        match = SIDECAR.match(raw.strip())
        if match is not None:
            return match.group("digest").lower()
    return None


def nist_sha_object(release, object_name):
     # NIST publishes a per-object .sha as a *separate* S3 object on the
     # per-Release path -- fetching it independently of the zip is what makes
     # layer 1 non-circular.
    url = f"{NIST_BASE}/rds_{release}/{object_name}.sha"
    with urllib.request.urlopen(url, timeout=60) as handle:
        return handle.read().decode("utf-8")


def extract_delta_sql(delta, target):
    # Pull a real Delta .sql from its zip, streamed (no full unzip).
    name = "RDS_" + delta + "_" + FAMILY + "_delta.zip"
    with zipfile.ZipFile(RAW / name) as zf:
        inner = [n for n in zf.namelist() if n.endswith(".sql")][0]
        with zf.open(inner) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out, length=1024 * 1024)
    return target


def extract_delta_zip(delta, dest):
    # Extract a real Delta zip for the layer-2 inner-signature check.
    name = "RDS_" + delta + "_" + FAMILY + "_delta.zip"
    with zipfile.ZipFile(RAW / name) as zf:
        zf.extractall(dest)
    return dest / ("RDS_" + delta + "_" + FAMILY + "_delta")


def capped_prefix(sql_path, cap):
    # A line-bounded subset: first `cap` INSERT rows wrapped in a single
    # transaction, so the large-delta apply is exercised without the volume.
    rows = []
    with open(sql_path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line.upper().startswith("INSERT INTO FILE"):
                rows.append(line if line.endswith(";") else line + ";")
                if len(rows) >= cap:
                    break
    return ["BEGIN TRANSACTION"] + rows + ["COMMIT"]


def build_base(path, sample_sql, base_rows):
    # A real-schema FILE table + DISTINCT_HASH view seeded with `base_rows` rows
    # sampled from a real Delta, so the volume has real rows first.
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE FILE (sha256 VARCHAR, sha1 VARCHAR, md5 VARCHAR, "
            "crc32 VARCHAR, file_name VARCHAR, file_size INTEGER, "
            "package_id INTEGER)")
        conn.execute(
            "CREATE VIEW DISTINCT_HASH AS SELECT DISTINCT sha256, sha1, "
            "md5, crc32 FROM FILE")
        with open(sample_sql, encoding="utf-8") as handle:
            n = 0
            for raw in handle:
                statement = raw.strip()
                if statement.upper().startswith("INSERT INTO FILE"):
                    conn.execute(
                        statement
                        if statement.endswith(";") else statement + ";")
                    n += 1
                    if n >= base_rows:
                        break
        conn.commit()
    finally:
        conn.close()


def count_file_rows(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM FILE").fetchone()[0]
    finally:
        conn.close()


def newest_digest(db_path):
    # A real digest in FILE -- proves the apply inserted rows.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT sha256 FROM FILE WHERE sha256 IS NOT NULL "
            "ORDER BY rowid DESC LIMIT 1").fetchone()
        return row[0].upper() if row else ""
    finally:
        conn.close()


def main():
    start_rss = peak_rss_mib()
    work = HERE / ".." / "proof_work_bounded"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    data = work / "data"
    data.mkdir(parents=True)
    delta_sql = {}

    try:
        # -- Layer 1: real streamed zip SHA-1 == NIST .sha sidecar --
        rzip = RAW / f"RDS_{RELEASE}_{FAMILY}.zip"
        l1 = sha1_stream(rzip) == sidecar_digest(
            rzip.with_suffix(rzip.suffix + ".sha"))
        check("layer 1: streamed zip SHA-1 == NIST .sha sidecar (real 18 GiB)",
              l1)

        # -- Extract both real Delta .sql (streamed; small on disk) --
        for delta in DELTAS:
            delta_sql[delta] = extract_delta_sql(delta, work / f"{delta}.sql")

        # -- Layer 2: real inner SHA-256 == inner signatures.txt --
        inner = extract_delta_zip(DELTAS[0], work / "inner")
        sigs = inner / "signatures.txt"
        check("layer 2: inner SHA-256 of real Delta .sql == signatures.txt",
              provision.verify_signatures(inner, sigs) is True)

        # -- Build a small base from real rows, then turnkey-apply --
        base = str(work / "base.db")
        build_base(base, delta_sql[DELTAS[0]], CAP // 2)
        base_set = hasheset.provision(base,
                                      hasheset.Provenance("modern", RELEASE))
        ordered = [(d, capped_prefix(delta_sql[d], CAP)) for d in DELTAS]
        t0 = time.time()
        current = base_set
        for release_name, sql in ordered:
            current = hasheset.apply_delta(current, sql, release_name)
        out = current.path
        rows = count_file_rows(out)
        check("turnkey apply: streamed+batched real Deltas applied",
              rows >= 2 * CAP,
              f"{rows} rows / {time.time() - t0:.1f}s / cap {CAP} x2")

         # -- Layer 3: record the REAL NIST published token (attest) --
        token = provision.read_published_dbhash(
            RAW / "dbhashes.2026.09.1.txt", FINAL_DB)
        check("layer 3: real NIST dbhash read from dbhashes.txt",
              token == PUBLISHED_TOKEN, "token=" + str(token))

          # The volume the service loads: the token is attached at provision
          # time (as provision_release / boot do). provision_release copies the
          # applied db into the data dir as rds.db; mirror that disk step so
          # boot finds the mounted Hash Set beside its manifest.
        volume_db = str(data / "rds.db")
        shutil.copyfile(current.path, volume_db)
        hash_set = hasheset.provision(
            volume_db, hasheset.Provenance("modern", RELEASE,
                                      tuple(current.provenance.deltas),
                                      token))

        known = newest_digest(volume_db)
        unknown = "0" * 64
        check("delta apply: inserted digest is KNOWN",
              hash_set.is_known("sha256", known), known[:16])
        check("unknown digest is UNKNOWN",
              not hash_set.is_known("sha256", unknown))

         # -- Write the manifest, confirm readiness, boot + /check --
        record = provision.write_manifest(
            data / "manifest.json", "modern", RELEASE,
            list(hash_set.provenance.deltas), token)
        check("manifest records real token + ordered deltas",
              record["dbhash"] == PUBLISHED_TOKEN
              and record["deltas"] == DELTAS, str(record["deltas"]))
        check("readiness gate: manifest agrees with mounted Hash Set",
              hasheset.verify_readiness(record, hash_set) is True)

        boot.bootstrap(data_dir=str(data), audit_dir=str(data))
        client = app.api.test_client()
        check("/health reports ready",
              client.get("/health").get_json().get("ready") is True)
        resp = client.post("/check",
                           json={"algorithm": "sha256",
                                 "hashes": [known, unknown]}).get_json()
        by = {r["digest"].upper(): r for r in resp["results"]}
        check("/check: KNOWN answer carries real token",
              by[known]["status"] == "known"
              and by[known]["dataset"]["dbhash"] == PUBLISHED_TOKEN)
        check("/check: UNKNOWN answer carries same real token",
              by[unknown]["status"] == "unknown"
              and by[unknown]["dataset"]["dbhash"] == PUBLISHED_TOKEN)
        app.configure(None)

        ok = all(result for result, _label in CHECKS)
        print("=== BOUNDED REAL-DATA TURNKEY PROOF: "
              + ("ALL PASS" if ok else "FAILURES") + " ===")
        print(f"peak RSS delta: {peak_rss_mib() - start_rss:.1f} MiB")
        print("volume: " + str(data))
        return 0 if ok else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
