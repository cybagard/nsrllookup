"""Real-data proof of the turnkey path (prod-functional ticket 04).

Proves `make provision` / the turnkey driver on NIST's *real* RDS V3 Minimal
artifacts for the current 2026.09.1 Minimal **Set**: full base Release
`RDS_2026.03.1` + ordered Deltas `2026.06.1` then `2026.09.1`, whose final
post-delta database `RDS_2026.09.1_modern_minimal.db` NIST publishes a real
`dbhash` for (`481e5f55f6d1ed63ea0f176779efc5cc5d53e52a`). This closes the
open strand `rds-v3-live/07(b)` left: that release (a 2021 *curated* set)
predated `dbhashes.txt`, so no real token existed to check; here layer 3 is
NIST's *real published* token, recorded -- not a stand-in.

What is exercised for real
--------------------------
* **Layer 1** zip **SHA-1** vs each `.sha` sidecar (real zips, real sidecars).
* **Layer 2** inner **SHA-256** vs each zip's inner `signatures.txt`.
* **Layer 3** NIST's published **`dbhash`** read from the real `dbhashes.txt`
  and recorded in the **Provisioning manifest** (ADR-0006: attested, not
  recomputed -- NIST's binary/algorithm is not public).
* The ordered **Delta** apply (copy + `executescript`), Sidecar index rebuild,
  and the **Provisioning manifest** write.
* A **service boot** (`boot.bootstrap`) against the resulting volume: `/health`
  reports **`ready`** and `/check` answers carry the real token in the
  **Lookup Result** `dataset` block.

What remains the operator's step
--------------------------------
The multi-gigabyte **Release** fetch (~18 GiB `RDS_2026.03.1` full zip) and the
production host. This proof runs out of CI: it reads the artifacts already
fetched into `raw/` through a local disk-backed opener (standing in for the
operator's download -- same exact-name contract `fetch_set` uses), so no
multi-GB I/O transits the pipeline (ADR-0003).
"""

import hashlib
import os
import sys
from pathlib import Path

RAW = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw"))
API = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "api"))
sys.path.insert(0, str(API))

import boot   # noqa: E402
import app    # noqa: E402
import driver # noqa: E402
import provision   # noqa: E402

RELEASE = "2026.03.1"
DELTAS = ["2026.06.1", "2026.09.1"]
TERMINAL = "2026.09.1"
FAMILY = "modern_minimal"
PUBLISHED_TOKEN = "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
FINAL_DB = "RDS_2026.09.1_modern_minimal.db"

# A real digest the 2026.09.1 Delta INSERTS into FILE -- so it is KNOWN only
# after the deltas apply (proves the apply), vs a value NIST never publishes.
KNOWN_SHA256 = "00000296EB569C19B0F2BD73B481392A76A0B4DC6FEBD52483E967D12F41AE50"
UNKNOWN_SHA256 = "00" * 32


class _LocalHandle:
        # A urllib-style opened object backed by the operator's already-fetched
        # NIST artifact, streamed from disk in chunks and returning b"" at EOF
        # (same contract as urllib.request.urlopen). The multi-gigabyte release
        # zip is copied chunked, never read whole into process memory.
    def __init__(self, path):
        self._f = open(path, "rb")

    def read(self, size=-1):
        return self._f.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self._f.close()
        return False


def local_opener(url):
        # The fetch stage stood in by the operator's download: resolve the exact
        # NIST object name to its local copy under raw/ (the disk-backed stand-in
        # for S3's per-Release path). A miss raises, matching a real URLError.
    import urllib.error
    name = Path(url).name
    target = RAW / name
    if name == "dbhashes.txt":
        target = RAW / "dbhashes.2026.09.1.txt"
    if not target.exists():
        raise urllib.error.URLError("no local artifact for " + name)
    return _LocalHandle(target)


def main():
    results = []

    def check(label, ok, detail=""):
        results.append((bool(ok), label))
        print(("PASS " if ok else "FAIL ") + label
             + ((" -- " + detail) if detail else ""))

    work = RAW.parent / "proof_work"
    data = RAW.parent / "proof_data"
    for d in (work, data):
        if d.exists():
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    # ---- THE TURNKEY RUN: fetch + verify 3 layers + apply + record + write ----
    hash_set, record = driver.provision_release(
         RELEASE, DELTAS,
          data_dir=str(data),
           work_dir=str(work),
           family=FAMILY,
          set_name="modern",
          opener=local_opener)

    check("turnkey run completed (fetch+verify+apply+record+write)",
          record is not None, "released vol -> " + str(data))
    # The manifest is the integrity attestation a forensic consumer re-checks.
    check("manifest records NIST's REAL published dbhash (not a stand-in)",
          record["dbhash"] == PUBLISHED_TOKEN,
          "recorded " + record["dbhash"])
    check("manifest recipe: base + ordered deltas",
          record["release"] == RELEASE and record["deltas"] == DELTAS,
          str(record["release"]) + " + " + str(record["deltas"]))
    # The delta apply is real: the 2026.09.1-inserted digest is now KNOWN.
    check("delta apply: 2026.09.1-inserted digest is KNOWN in the final Set",
          hash_set.is_known("sha256", KNOWN_SHA256))
    check("the absent digest is UNKNOWN (lookup still discriminates)",
          not hash_set.is_known("sha256", UNKNOWN_SHA256))

    # ---- THE SERVICE BOOT: an operator's `make verify` + app startup ----
    verify = driver.verify_release(str(data))
    check("make verify: the provisioned volume is READY", verify.ready,
          str(verify.checks))

    loaded, manifest = boot.bootstrap(data_dir=str(data))
    client = app.api.test_client()
    health = client.get("/health").get_json()
    check("/health reports ready",
          health.get("ready") is True, "dataset=" + str(health.get("dataset")))
    # Every Lookup Result carries the dataset -- the recorded token rides on it.
    resp = client.post(
         "/check",
         json={"algorithm": "sha256",
               "hashes": [KNOWN_SHA256, UNKNOWN_SHA256]})
    payload = resp.get_json()
    known = [r for r in payload["results"]
             if r["digest"].upper() == KNOWN_SHA256][0]
    unknown = [r for r in payload["results"]
               if r["digest"].upper() == UNKNOWN_SHA256][0]
    check("/check: KNOWN answer + dbhash in its dataset block",
          known["status"] == "known"
          and known["dataset"]["dbhash"] == PUBLISHED_TOKEN,
          "dbhash=" + known["dataset"]["dbhash"])
    check("/check: UNKNOWN answer + same real token",
          unknown["status"] == "unknown"
          and unknown["dataset"]["dbhash"] == PUBLISHED_TOKEN,
          "dataset=" + str(unknown["dataset"]))

    ok = all(r[0] for r in results)
    print("=== REAL-DATA TURNKEY PROOF: "
          + ("ALL PASS" if ok else "FAILURES") + " ===")
    print("final volume: " + str(data))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
