# 04: Confirm the RDS V3 on-disk layout

**What to build:** a confirmed view of NIST RDS V3's on-disk **Set** layout (a research
spike) precise enough to build a fixture **Hash Set**, without unpacking a multi-gigabyte
release into the repo. Schema is already known from NIST's V3 doc (SQLite; a per-file
metadata table with the digests; digests stored UPPERCASE; no standalone hash index — which
is *why* a per-Algorithm index exists).

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] The Minimal **Set**'s database/schema is documented: the per-file table and its
      digest columns (MD5, SHA-1, SHA-256; CRC-32 present but unused), case, and the
      absence of a standalone hash index.
- [x] A small sample (tiny enough to live in the repo as a fixture) is captured so ticket 05
      can build a fixture **Hash Set** for MD5, SHA-1, and SHA-256 lookups.
- [x] Confirms the "no standalone hash index" observation that motivates the per-Algorithm
      index in ticket 05.

## Comments

Closed via `api/hasheset.py` (schema constants + `build_minimal_fixture_db`) and
`api/tests/test_hasheset_layout.py` (layout smoke check), added in `5274666`. The module
docstring documents the `METADATA` table, the `crc32/md5/md5sha1/sha1/sha256/filename`
column order, the UPPERCASE digest storage, and the absence of a standalone hash index;
`test_no_standalone_hash_index` asserts it, and `build_minimal_fixture_db` produces the
tiny in-repo sample ticket 05 consumes.

## Superseded

This ticket "confirmed" a schema that turns out to be **synthetic**, not NIST's. The
`rds-v3-live` effort byte-confirms NIST's **real** Minimal layout from the shipped
`schema.sql` (release 2026.09.1): the per-file table is **`FILE`**, not `METADATA`;
there is **no `md5sha1`** column; the filename column is **`file_name`**, not `filename`;
and `FILE` also carries **`file_size`** and **`package_id`**. The real layout is
`FILE(sha256, sha1, md5, crc32, file_name, file_size, package_id)` plus a
`DISTINCT_HASH(sha256, sha1, md5, crc32)` **view**. See
`../rds-v3-live/issues/01-confirm-real-schema.md` (resolved; answer + evidence in
`../rds-v3-live/artifacts/`). This ticket's data-layer claim is superseded; its
test-runner/migration work is not.
