# 04: Confirm the RDS V3 on-disk layout

**What to build:** a confirmed view of NIST RDS V3's on-disk **Set** layout (a research
spike) precise enough to build a fixture **Hash Set**, without unpacking a multi-gigabyte
release into the repo. Schema is already known from NIST's V3 doc (SQLite; a per-file
metadata table with the digests; digests stored UPPERCASE; no standalone hash index — which
is *why* a per-Algorithm index exists).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The Minimal **Set**'s database/schema is documented: the per-file table and its
      digest columns (MD5, SHA-1, SHA-256; CRC-32 present but unused), case, and the
      absence of a standalone hash index.
- [ ] A small sample (tiny enough to live in the repo as a fixture) is captured so ticket 05
      can build a fixture **Hash Set** for MD5, SHA-1, and SHA-256 lookups.
- [ ] Confirms the "no standalone hash index" observation that motivates the per-Algorithm
      index in ticket 05.

## Comments
