"""Real-data proof of the turnkey path, UNCAPPED, on a small machine.

Proves `make provision` / the turnkey driver on NIST's *real* RDS V3 Minimal
artifacts for the current 2026.09.1 Minimal **Set**: full base Release
`RDS_2026.03.1` + ordered Deltas `2026.06.1` then `2026.09.1`, whose final
post-delta database NIST publishes a real `dbhash` for
(`481e5f55f6d1ed63ea0f176779efc5cc5d53e52a`). Everything is unbounded: the
full 181.833 GB base .db inside the 18.775 GB archive, the in-database hash
index over all ~438M FILE rows, both real Delta applies, the published
token, the verify/boot/lookup gate.

How it fits a small machine (ADR-0007)
--------------------------------------
The uncapped run's disk peak is *bounded at one full database plus the
archive* (~260 GiB on one volume for this Set): the driver applies the
Deltas in place on its scratch working copy, publishes by same-volume
rename, and resumes objects already on disk. It never doubles or triples the
database (the old pipeline peaked at 500-730 GiB, which is what took the
Docker VM's ext4 down with a write-EIO storm at 07:17Z). RAM stays bounded
(streaming digests, batched applies, in-DB index); the run is pre-flighted
against the free volume and monitored with a measured peak + free floor.

Where it runs
-------------
In the dev container (python:3.14-slim), out of CI. `raw/` is the
operator-fetched NIST set (ADR-0003: the multi-GB download is the operator's
step); the fetch stage runs for real and *resumes* from it (nothing is
re-copied). The heavy I/O lands on the mounted workspace volume, never on the
VM's own disk. The proof records a measured footprint (sizes, allocated
blocks vs logical size -- the zero-tail check -- free space, peak RSS) so
the ticket closes with numbers, not estimates.
"""

import argparse
import os
import resource
import shutil
import sys
import threading
import time
import urllib.error
import zipfile
from pathlib import Path

RAW = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw"))
API = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "..", "api"))
sys.path.insert(0, str(API))

import app    # noqa: E402
import boot   # noqa: E402
import driver # noqa: E402
import provision   # noqa: E402

RELEASE = "2026.03.1"
DELTAS = ["2026.06.1", "2026.09.1"]
TERMINAL = "2026.09.1"
FAMILY = "modern_minimal"
PUBLISHED_TOKEN = "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
FINAL_DB = "RDS_" + TERMINAL + "_" + FAMILY + ".db"
RZIP = "RDS_" + RELEASE + "_" + FAMILY + ".zip"

# A real digest the 2026.09.1 Delta INSERTS into FILE (the first row of its
# real `.sql`) -- so it is KNOWN only after the deltas apply -- vs a value
# NIST never publishes.
KNOWN_SHA256 = "00000296EB569C19B0F2BD73B481392A76A0B4DC6FEBD52483E967D12F41AE50"
UNKNOWN_SHA256 = "00" * 32

GB = 1e9
GiB = 1 << 30
INDEX_BUDGET = 80 * GB   # in-DB hash index growth seen on real data
SLACK = 30 * GB          # headroom the pre-flight gate demands
FLOOR = 20 * GB          # free space that must survive the whole run

DATA = RAW.parent / "proof_data"
EXTRACTED = RAW / "extracted"


def _gb(nbytes):
    return "%.1f GiB" % (nbytes / GiB)


def free_bytes():
    # Volume free space the run may use. Inside the dev container the
    # workspace is Docker Desktop's file share, whose `statvfs` fakes a
    # synthetic ~140 TiB figure -- untrustworthy -- so a host-side sample,
    # injected as HOST_FREE_BYTES at launch, wins when present.
    env = os.environ.get("HOST_FREE_BYTES")
    if env:
        return int(env)
    st = os.statvfs(RAW)
    return st.f_bavail * st.f_bsize


def file_footprint(path):
    # Logical size + allocated blocks. blocks << size means a zero tail
    # (sparse/holey file) -- the check the run records before the 237.4 GiB
    # figure may be trusted.
    st = os.lstat(path)
    return st.st_size, st.st_blocks * 512


def all_dbs():
    for root in (RAW, DATA):
        if root.exists():
            for path in root.rglob("*.db"):
                yield path


class Monitor(threading.Thread):
    """Sample the run's volume while the driver does its multi-hour I/O.

    Records the *measured* peak of allocated blocks (real disk in use, so a
    sparse file would not inflate it) and the lowest free-space reading, so
    the footprint the ticket records is what the run did, not the design
    estimate.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self.n = 0
        self.peak_alloc = 0
        self.min_free = float("inf")

    def run(self):
        while not self._stop.wait(5):
            alloc = 0
            for path in all_dbs():
                alloc += path.lstat().st_blocks * 512
            self.peak_alloc = max(self.peak_alloc, alloc)
            self.min_free = min(self.min_free, free_bytes())
            self.n += 1
            if self.n % 60 == 1:   # one line ~ every 5 min
                print("[%s] monitor: peak_alloc=%s free=%s" % (
                    time.strftime("%H:%M:%S"), _gb(self.peak_alloc),
                    _gb(self.min_free)), flush=True)

    def stop(self):
        self._stop.set()
        self.join(timeout=15)


def pre_flight():
    """Demand the run fits *before* it writes a byte.

    The uncapped run needs, on one volume: the archive (already present),
    the extracted base (its real zip central-directory size), the in-DB hash
    index, plus slack. A machine that cannot hold this is refused here --
    not allowed to fail mid-extraction with a half-written database, which
    is how the earlier crash left 187 GiB of detritus.
    """
    with zipfile.ZipFile(RAW / RZIP) as zf:
        base = sum(i.file_size for i in zf.infolist()
                   if i.filename.endswith(".db"))
    free = free_bytes()
    need = base + INDEX_BUDGET + SLACK
    print("pre-flight: base=%.1f GiB  index_budget=%d GiB  slack=%d GiB"
          % (base / GiB, INDEX_BUDGET / GiB, SLACK / GiB), flush=True)
    print("pre-flight: need=%s  volume_free=%s"
          % (_gb(need), _gb(free)), flush=True)
    ok = free >= need
    print("pre-flight: %s" % ("OK" if ok else "FAIL -- not enough volume"),
          flush=True)
    return ok


class _LocalHandle:
    # A urllib-style opened object backed by the operator's already-fetched
    # NIST artifact, streamed from disk in chunks and returning b"" at EOF
    # (same contract as urllib.request.urlopen). The multi-gigabyte release
    # zip is never read whole into process memory.

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
    # The fetch stage, stood in by the operator's download: resolve the exact
    # NIST object name to its local copy under raw/ (the disk-backed stand-in
    # for S3's per-Release path -- the objects themselves are NIST's real
    # ones). A miss raises, matching a real URLError.
    name = Path(url).name
    target = RAW / name
    if name == "dbhashes.txt":
        target = RAW / "dbhashes.2026.09.1.txt"
    if not target.exists():
        raise urllib.error.URLError("no local artifact for " + name)
    return _LocalHandle(target)


def _find_delta_sql(release):
    name = "RDS_" + release + "_" + FAMILY + "_delta.sql"
    if EXTRACTED.exists():
        for path in EXTRACTED.rglob(name):
            return path
    return None


def _sql_contains(release, digest):
    # Stream-scan a Delta `.sql` (one line at a time) for `digest`.
    path = _find_delta_sql(release)
    if path is None:
        return None
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if digest in line:
                return True
    return False


def _cleanup():
    shutil.rmtree(DATA, ignore_errors=True)
    shutil.rmtree(EXTRACTED, ignore_errors=True)
    (RAW / "base.db").unlink(missing_ok=True)
    (RAW / "dbhashes.txt").unlink(missing_ok=True)
    print("cleaned: proof volume + scratch removed; NIST zips retained "
          "in raw/", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Uncapped real-data proof of the turnkey path")
    parser.add_argument(
        "--keep", action="store_true",
        help="keep the provisioned volume afterwards (default: remove it)")
    args = parser.parse_args(argv)

    results = []

    def check(label, ok, detail=""):
        results.append((bool(ok), label))
        print(("PASS " if ok else "FAIL ") + label
              + (("  -- " + detail) if detail else ""), flush=True)

    if DATA.exists():
        shutil.rmtree(DATA, ignore_errors=True)
    if not pre_flight():
        print("aborting before the heavy I/O (ADR-0007)", flush=True)
        return 2

    monitor = Monitor()
    monitor.start()
    t0 = time.time()

    try:
        # ---- THE TURNKEY RUN: fetch + verify 3 layers + apply + record ----
        hash_set, record = driver.provision_release(
            RELEASE, DELTAS,
            data_dir=str(DATA), work_dir=str(RAW),
            family=FAMILY, set_name="modern", opener=local_opener)
    except BaseException:
        monitor.stop()
        if not args.keep:
            _cleanup()
        raise
    run_secs = time.time() - t0
    monitor.stop()

    check("turnkey run completed (fetch+verify+apply+record+write)",
          record is not None, "%.1f min" % (run_secs / 60.0))

    final = DATA / "rds.db"
    size, used = file_footprint(final)
    check("final volume fully materialised (zero tail verified)",
          used + 8192 >= size,
          "size=%s allocated=%s" % (_gb(size), _gb(used)))
    check("manifest records NIST's REAL published dbhash (not a stand-in)",
          record["dbhash"] == PUBLISHED_TOKEN, "recorded " + record["dbhash"])
    check("manifest recipe: base + ordered deltas",
          record["release"] == RELEASE and record["deltas"] == DELTAS,
          record["release"] + " + " + str(record["deltas"]))
    check("delta apply: 2026.09.1-inserted digest is KNOWN in the final Set",
          hash_set.is_known("sha256", KNOWN_SHA256))
    check("the absent digest is UNKNOWN (lookup still discriminates)",
          not hash_set.is_known("sha256", UNKNOWN_SHA256))
    check("KNOWN digest is a 2026.09.1 insertion (in that delta, not 2026.06.1's)",
          _sql_contains(TERMINAL, KNOWN_SHA256) is True
          and _sql_contains(DELTAS[0], KNOWN_SHA256) is False)

    # ---- THE SERVICE BOOT: an operator's `make verify` + app startup ----
    verify = driver.verify_release(str(DATA))
    check("make verify: the provisioned volume is READY", verify.ready,
          str(verify.checks))

    audit = DATA / "audit"
    audit.mkdir(exist_ok=True)
    loaded, manifest = boot.bootstrap(
        data_dir=str(DATA), audit_dir=str(audit))
    client = app.api.test_client()
    health = client.get("/health").get_json()
    check("/health reports ready",
          health.get("ready") is True, "dataset=" + str(health.get("dataset")))
    resp = client.post("/check", json={"algorithm": "sha256",
                                       "hashes": [KNOWN_SHA256,
                                                  UNKNOWN_SHA256]})
    payload = resp.get_json()
    known = next(r for r in payload["results"]
                 if r["digest"].upper() == KNOWN_SHA256)
    unknown = next(r for r in payload["results"]
                   if r["digest"].upper() == UNKNOWN_SHA256)
    check("/check: KNOWN answer + dbhash in its dataset block",
          known["status"] == "known"
          and known["dataset"]["dbhash"] == PUBLISHED_TOKEN,
          "dbhash=" + known["dataset"]["dbhash"])
    check("/check: UNKNOWN answer + same real token",
          unknown["status"] == "unknown"
          and unknown["dataset"]["dbhash"] == PUBLISHED_TOKEN,
          "dataset=" + str(unknown["dataset"]))

    # ---- MEASURED FOOTPRINT (the numbers the ticket records) ----
    print("=== measured footprint ===", flush=True)
    print("run time:       %.1f min" % (run_secs / 60.0), flush=True)
    print("peak allocated: %s (monitored)" % _gb(monitor.peak_alloc),
          flush=True)
    print("min free:       %s (monitored)" % _gb(monitor.min_free),
          flush=True)
    print("final volume:   size=%s allocated=%s"
          % (_gb(size), _gb(used)), flush=True)
    print("peak RSS:       %s MiB"
          % (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0),
          flush=True)
    check("disk peak bounded: archive + one database, never a third",
          monitor.peak_alloc <= size * 2 + 30 * GiB,
          "peak=%s (final=%s)" % (_gb(monitor.peak_alloc), _gb(size)))

    if args.keep:
        print("keeping the provisioned volume at " + str(DATA), flush=True)
    else:
        print("removing the 237 GiB proof volume to return the space"
              " (re-run proves it again; `--keep` retains it)", flush=True)
        _cleanup()

    ok = all(r[0] for r in results)
    print("=== REAL-DATA TURNKEY PROOF (UNCAPPED): "
          + ("ALL PASS" if ok else "FAILURES") + " ===", flush=True)
    for passed, label in results:
        if not passed:
            print("failed: " + label, flush=True)
    print("final volume: " + str(final), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
