# 01: Byte-confirm the real NIST Minimal `FILE`/`DISTINCT_HASH` schema

**What to build:** a confirmed view of NIST's **real** RDS V3 **Minimal** on-disk layout —
superseding ticket `04` of `rds-v3-migration`, which "confirmed" a synthetic `METADATA`
table that NIST does not publish. From NIST's shipped `schema.sql`/`signatures.txt` (the
~206 MiB `RDS_<ver>_<set>_minimal_delta.zip` ships both) record the authoritative schema:
the `FILE` table columns, the `DISTINCT_HASH` view, the absence of `md5sha1`, `file_name`
vs `filename`, and the digest casing.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The real **Minimal** `FILE` table is documented with its authoritative column set
       (`sha256, sha1, md5, crc32, file_name, file_size, package_id`) and the `DISTINCT_HASH`
        view (`sha256, sha1, md5, crc32`).
- [ ] The `METADATA`/`md5sha1`/`filename` synthetic layout is **refuted**: confirmed absent
       from the real schema, with a pointer from this ticket to ticket `04` as superseded.
- [ ] Digest **casing** in the real db is recorded (expected UPPERCASE in presentation;
        confirm stored form), so ticket 02 can fix the normalisation side.
- [ ] The confirmation cites the NIST artifact it came from (shipped `schema.sql`), recorded
        for ticket 02 to rebuild the fixture in the real shape.
