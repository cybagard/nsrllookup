"""RAM-scaled proof that the in-database hash index is memory-bounded.

Builds fixture FILE tables of increasing size and measures the peak RSS
while building the index + running lookups. Under the old design the RSS
grew with the distinct-digest count (an in-RAM `Set[str]` per algorithm,
materialised from DISTINCT_HASH) -- the OOM. Now the membership index is a
B-tree `CREATE INDEX` built *inside* the db and a lookup is an indexed
on-disk seek, so the build streams and the peak RSS stays flat: the digest
data lives in the database file, not in the process.
"""
import hashlib
import os
import resource
import sqlite3
import sys
import tempfile
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))
import hasheset


def peak_mib():
    # macOS reports ru_maxrss in bytes; POSIX in KB. Normalise to MiB.
    kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return kb / 1024 if kb > 1_000_000_000 else kb / 1024 / 1024


def main():
    for n in (50_000, 500_000, 5_000_000):
        d = tempfile.mkdtemp()
        dbp = os.path.join(d, "big.db")
        conn = sqlite3.connect(dbp)
        cols = ", ".join(f"{c} {t}" for c, t in hasheset.COLUMN_TYPES.items())
        conn.execute(f"CREATE TABLE {hasheset.TABLE} (\n{cols}\n)")
        ph = ", ".join("?" * 7)
        batch = []
        for i in range(n):
            h = hashlib.sha256(str(i).encode()).hexdigest()
            batch.append((h, h[:40], h[:32], str(i), str(i), 0, 0))
            if len(batch) >= 10000:
                conn.executemany(
                    f"INSERT INTO {hasheset.TABLE} VALUES ({ph})", batch)
                batch = []
        if batch:
            conn.executemany(
                f"INSERT INTO {hasheset.TABLE} VALUES ({ph})", batch)
        conn.execute(
            f"CREATE VIEW {hasheset.DISTINCT_HASH_VIEW} AS "
            "SELECT DISTINCT sha256, sha1, md5, crc32 "
            f"FROM {hasheset.TABLE}")
        conn.commit()
        conn.close()
        start = peak_mib()
        t0 = time.time()
        before = os.path.getsize(dbp)
        hs = hasheset.provision(
            dbp, hasheset.Provenance("modern", "2026.09.1", ["2026.06.1"]))
        first = hs.is_known("md5", "0" * 32)
        for i in range(1000):
            q = hashlib.md5(f"probe-{i}".encode()).hexdigest()
            hs.is_known("md5", q)
        elapsed = time.time() - t0
        peak = peak_mib()
         # The index is built inside the db; its O(N) cost shows up as db growth.
        index_bytes = os.path.getsize(dbp) - before
        print(f"rows={n:>9}  build+lookup {elapsed:6.2f}s   "
              f"peak_rss_delta={peak - start:6.1f} MiB   "
              f"known(000..)={first}  index={index_bytes // 1024} KiB")
        os.remove(dbp)


if __name__ == "__main__":
    main()
