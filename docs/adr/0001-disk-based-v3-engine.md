# Disk-based V3 lookup engine, not an embedded set

RDS V3 is a plain **SQLite** database, and the full Modern set is ~124 GB, so it cannot
be loaded into the API process. nsrllookup queries a mounted, read-only **Minimal set**
(~18 GB, plus **Delta releases** applied on top) directly with SQL, rather than embedding
it, streaming it, or routing through a separate daemon. We retire `nsrlsvr` and its
socket protocol (`nsrllookup.py`): V3 has no maintained `nsrlupdate`, and the database is
queryable as-is, so a custom engine collapses into "open the `.db`, run a query".

Because V3 stores digests UPPERCASE with **no standalone hash index**, a `WHERE
md5 = '…'` on ~940 M rows is a full scan. To keep lookups fast we **build a
hash index at ingest** -- one B-tree `CREATE INDEX` per supported Algorithm
(`idx_md5`, `idx_sha1`, `idx_sha256`), built when a Delta release is applied.

The index sits **inside the Hash Set's own `.db`**, not as a separate on-disk
artifact. A membership lookup is `SELECT 1 FROM FILE WHERE <column> = ? LIMIT 1`,
an indexed B-tree seek that is ~constant in N because the dataset is static after
provisioning -- and, crucially, it materialises **no in-RAM distinct-digest
set** (the OOM that a ~430 M-entry × 3-algorithm Python set would cause). Because
the index lives in the same file as the rows it covers, there is **no second
dataset** to ship, validate, or keep in sync: the mounted db is both the row
store and its index. `IF NOT EXISTS` builds make the index idempotent, so
provisioning over a base that already carries it (or a re-apply) is a no-op. The
index carries no fact the db lacks, and it does not recompute the dbhash:
that dataset-integrity token is attested from NIST's `dbhashes.txt`
(ADR-0006), not derived from the rows. We deliberately **do not** use a separate
on-disk sidecar copy of `DISTINCT_HASH`: a sidecar is a redundant derived copy
of information the db already holds, which reintroduces the two-source-of-truth
and staleness concern the db-attestation model (ADR-0006: trust the verified
mount, don't recompute) is trying to avoid -- and a read-only mount could not
rebuild it, so it would have to be shipped. Folding the index into the db gives
the same indexed seek with none of that cost.

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
