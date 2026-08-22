# Disk-based V3 lookup engine, not an embedded set

RDS V3 is a plain **SQLite** database, and the full Modern set is ~124 GB, so it cannot
be loaded into the API process. nsrllookup queries a mounted, read-only **Minimal set**
(~18 GB, plus **Delta releases** applied on top) directly with SQL, rather than embedding
it, streaming it, or routing through a separate daemon. We retire `nsrlsvr` and its
socket protocol (`nsrllookup.py`): V3 has no maintained `nsrlupdate`, and the database is
queryable as-is, so a custom engine collapses into "open the `.db`, run a query".

Because V3 stores digests UPPERCASE with **no standalone hash index**, a `WHERE
md5 = '…'` on ~940 M rows is a full scan. To keep lookups fast we **build a hash→known
index at ingest** (one sidecar index per supported Algorithm — MD5, SHA-1, SHA-256),
rebuilt when a Delta release is applied.

- **Status**: accepted
- **Considered Options**: embed the set in-process (rejected: even the minimal 18 GB is
  large; the full set is far too big); a custom `nsrlsvr`-style daemon over a new socket
  protocol (rejected: a V3-aware daemon is net new code for no benefit once we own the
  database — NIST's only official V3 tool is the V3→V2 text converter, which is a
  regression, not a path forward); convert V3→V2 text and keep `nsrlsvr` (rejected:
  abandons SHA coverage and is the legacy path NIST is moving away from); rely on raw SQL
  scans with no index (rejected: 940 M-row scans per lookup are too slow); cache only a
  subset (rejected: incomplete answers are worse for forensics than slow-but-complete ones,
  so we serve the full minimal set with an index).
- **Consequences**: the `svr/` service and the `nsrlsvr` socket protocol are deprecated
  (ticket 07); the engine is "query the mounted SQLite minimal set via a per-algorithm
  index", not a second service; ingestion provisions the minimal set and applies deltas
  (ticket 02), not the 124 GB full download; supported lookup algorithms are MD5, SHA-1,
  SHA-256 — CRC-32 is physically present in every row but not a supported lookup.
