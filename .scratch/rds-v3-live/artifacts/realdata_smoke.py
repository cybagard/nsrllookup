"""One-off, out-of-CI mechanics smoke for ticket 07 (b).

Proves the re-based reader + delta apply + `dbhash` against a real NIST database
that exists -- `RDS_2021.12.2_curated` (~86.9 MiB). This is a *mechanics* proof:
the curated release is a *different*, older schema (`METADATA` source table + a
6-column `FILE` view, no `DISTINCT_HASH` view, no `crc32` in `FILE`), so it proves
the `executescript` apply + index rebuild + `dbhash`/read path works on a real NIST
db, **not** a Minimal-layout proof. The Minimal layout is proven in (a) against
NIST's shipped `schema.sql`.

It runs no CI and is not part of the automated suite (real-data I/O is multi-GB).
The `dbhash` layer uses an ADR-0006 stand-in token function: `dbhash` is NIST's
external binary (not re-implemented, not installed here), and this 2021 release
predates the `dbhashes.txt` convention, so there is no NIST-published token to
check against -- the mechanic is exercised, not verified against NIST.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile

API_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "api")
sys.path.insert(0, API_DIR)

import hasheset  # noqa: E402
import lookup  # noqa: E402
import provision  # noqa: E402

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
CURATED_DB = "/tmp/nsrl_2021_12_2/RDS_2021.12.2_curated.db"

# A real digest already in the curated db (from the FILE view sample) and one that
# is NOT in the db, to show known vs unknown end to end.
KNOWN_SHA256 = "0F04A4EBBDCB843CB493D42BF48ABC2848BB8F3F05A346524C42E68951DDF769"
UNKNOWN_SHA256 = "00" * 32

# Obvious fake values, so the "now known after apply" assertion is unambiguous. A
# NIST-style Delta would add such a row to the per-file table.
NEW = {
    "sha256": "DEADBEEF" * 8,
    "sha1": "FEEDFACE" * 5,
    "md5": "CAFEBABE" * 4,
}


def add_distinct_hash_view(conn):
    """The one adaptation a non-Minimal layout needs to serve the reader.

    The Minimal layout ships a `DISTINCT_HASH(sha256,sha1,md5,crc32)` view that
    the Sidecar index materialises. The curated release has no such view and its
    `FILE` view carries no `crc32` column, so for this mechanics proof we add a
    DISTINCT view over the curated `FILE` view (3 digest columns). This is the
    reader seam; it is the only schema difference the mechanics must bridge.
    """
    conn.execute("CREATE VIEW DISTINCT_HASH AS "
                 "SELECT DISTINCT sha256, sha1, md5 FROM FILE")
    conn.commit()


def nist_style_delta_sql(object_id):
    """Render a NIST-style Delta `.sql`: an ordered INSERT into METADATA.

    The curated release's per-file table is `METADATA` (the very table the
    migration refuted for Minimal, proving the schema is genuinely different);
    its `FILE` view then projects the new row. This exercises ticket 04's
    `executescript`-based apply, not the Minimal `FILE` column set.
    """
    values = ("999999999, {oid}, 'smoke', '/opt', 'smoke.bin', '', 0, "
              "'CAFEBABE', '{md5}', '{sha1}', '{sha256}'")
    stmt = ("INSERT INTO METADATA "
             "(metadata_id, object_id, key_hash, path, file_name, extension, "
             "bytes, crc32, md5, sha1, sha256) VALUES ("
             + values + ")").format(oid=object_id, **NEW)
    return "BEGIN TRANSACTION;\n" + stmt + ";\nCOMMIT;\n"


def stand_in_dbhash(path):
    """ADR-0006 stand-in token function over the final db.

    Not NIST's `dbhash`; a self-computed token used only to exercise the verify
    mechanic. Real NIST verification is out of scope here (no binary, no published
    token for this release).
    """
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    results = []

    def check(label, ok, detail=""):
        results.append((ok, label))
        print(("PASS " if ok else "FAIL ") + label
              + (("   -- " + detail) if detail else ""))

    if not os.path.exists(CURATED_DB):
        print("curated db not present at", CURATED_DB)
        return 1

    work = tempfile.mkdtemp(prefix="nsrl_smoke_")
    try:
        # -- READER: real db, real per-algorithm index from the DISTINCT view --
        base_path = os.path.join(work, "base.db")
        shutil.copyfile(CURATED_DB, base_path)
        conn = sqlite3.connect(base_path)
        add_distinct_hash_view(conn)
        conn.close()

        set_obj = hasheset.provision(
            base_path,
            hasheset.Provenance("curated", "2021.12.2", dbhash=None))
        n_sha256 = len(set_obj._index["sha256"])
        check("reader: real db materialises a distinct-sha256 index",
              n_sha256 == 408811, "distinct sha256 = " + str(n_sha256))
        check("reader: a real digest is KNOWN",
              set_obj.is_known("sha256", KNOWN_SHA256))
        check("reader: an absent digest is UNKNOWN",
              not set_obj.is_known("sha256", UNKNOWN_SHA256))
        check("reader: membership is case-agnostic (lowercase resolves)",
              set_obj.is_known("sha256", KNOWN_SHA256.lower()))

        # Full per-result path through the lookup seam.
        looked = lookup.look_up(set_obj, [KNOWN_SHA256, UNKNOWN_SHA256], "sha256")
        check("lookup: per-result path yields known + unknown with provenance",
              looked[0]["status"] == "known"
              and looked[1]["status"] == "unknown"
              and looked[0]["dataset"]["set"] == "curated")

        # -- DELTA APPLY: NIST-style .sql via the real executescript seam --
        obj_conn = sqlite3.connect(base_path)
        obj_id = obj_conn.execute(
            "SELECT object_id FROM PACKAGE_OBJECT LIMIT 1").fetchone()[0]
        obj_conn.close()
        delta_sql = nist_style_delta_sql(obj_id)
        applied = hasheset.apply_delta(
            set_obj, delta_sql, "2021.12.2-smoke", set_name="curated")
        check("delta apply: new digest becomes KNOWN after apply",
              applied.is_known("sha256", NEW["sha256"]))
        check("delta apply: base is untouched (new digest still unknown there)",
              not set_obj.is_known("sha256", NEW["sha256"]))
        check("delta apply: provenance carries the ordered delta",
              "2021.12.2-smoke" in applied.provenance.deltas)

        # -- DBHASH: the verify mechanic via an ADR-0006 stand-in --
        token = stand_in_dbhash(applied.path)
        check("dbhash: verify_dbhash accepts the matching token",
              provision.verify_dbhash(applied.path, token, stand_in_dbhash)
              is True)
        check("dbhash: verify_dbhash refuses a mismatched token",
              provision.verify_dbhash(applied.path, "0" * 64, stand_in_dbhash)
              is False)
        print("NOTE  dbhash: no NIST-published token for 2021.12.2_curated -- "
              "the mechanic (verify_dbhash) is exercised with an ADR-0006 "
              "stand-in; it is NOT verified against NIST this session.")

        # -- PROVISION + MANIFEST: the out-of-CI write the Provisioner does --
        manifest_path = os.path.join(work, "manifest.json")
        record = provision.write_manifest(
            manifest_path, "curated", "2021.12.2",
            applied.provenance.deltas, token)
        print("--- provisioned manifest (written out of CI) ---")
        print(json.dumps(record, indent=2))

        ok = all(r[0] for r in results)
        print("=== MECHANICS SMOKE: " + ("ALL PASS" if ok else "FAILURES") + " ===")
        return 0 if ok else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
