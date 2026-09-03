# nsrllookup

A forensic lookup service that answers whether a file digest is a "known" reference
data file, by checking it against the NIST Reference Data Set. It is a reference for
identifying the benign, pre-existing files in a digital-evidence corpus, so that
investigators can separate them from the files of interest.

## Language

### The data

**Reference Data Set (RDS)**:
The versioned collection of reference digests, published by NIST, that defines what
counts as "known". NIST publishes it in four **Sets** (Modern, Legacy, Android, iOS),
each as versioned RDS V3 releases. A release is identified by a date-version
(`2026.03.1`); the release consulted is part of the answer, not an implementation detail.
_Avoid_: hash set (use Set), database

**Set**:
One of NIST's four RDS collections — Modern, Legacy, Android, iOS. **Modern** is the set
that covers current ("modern") software; it is the set nsrllookup serves. The name
"modern" is the proper name of one Set, not an adjective for "the latest release".

**Minimal set**:
NIST's compact form of a Set — a smaller, deduplicated archive (e.g. ~18 GB for Modern)
as opposed to the full set (e.g. ~124 GB). nsrllookup serves the Minimal set.
_Avoid_: light set, slim db

**Release**:
One dated version of a Set, identified by a date-version (e.g. `2026.03.1`). NIST
publishes quarterly: a full **Release** in March, and **Delta releases** in June,
September, December.

**Delta release**:
An incremental update in NIST's own form — an ordered `.sql` script of
`INSERT`/`UPDATE`/`DELETE` statements — applied in order against a full Release's database
to reproduce the most current dataset without re-fetching the full set. A delta applies only
to the matching set.
_Avoid_: patch, upgrade

**Hash Set**:
The single current dataset nsrllookup has loaded and made queryable: one full **Release**
plus any **Delta releases** applied on top of it, in one versioned database. A **Provisioner**
produces it; the service loads it, read-only.
_Avoid_: server, daemon, database

**Digest**:
A hash value of a file at one algorithm (MD5, SHA-1, SHA-256). A Digest is one
algorithm's worth of a file's identity; algorithms are distinct and not interchangeable.
_Avoid_: hash (when the algorithm is unstated), md5 (when meaning "a digest" generally),
crc32 (not a supported lookup algorithm — see Digests)

**Algorithm**:
One of the digest algorithms nsrllookup accepts: **MD5**, **SHA-1**, or **SHA-256**. A
lookup is always per-algorithm: a file may be "known" under MD5 independently of whether
it is "known" under SHA-256. An RDS row physically carries **CRC-32** as well, but
nsrllookup does not accept CRC-32 lookups — it is a weak, non-forensic checksum.
_Avoid_: digest (when meaning the algorithm), "crc32" (not a supported lookup)

**Set schema**:
The on-disk shape of a Minimal **Set**: a `FILE` table
(`sha256, sha1, md5, crc32, file_name, file_size, package_id`) and a `DISTINCT_HASH`
(`sha256, sha1, md5, crc32`) view over it. `crc32` is a physical column but not a lookup
**Algorithm**.
_Avoid_: METADATA table (the per-file table is `FILE`), md5sha1 (no such column),
filename (the column is `file_name`)

**Sidecar index**:
nsrllookup's own membership index — the distinct digests materialised from the
`DISTINCT_HASH` view (per **Algorithm**), persisted alongside the mounted Hash Set. It is
replaced when a **Delta release** is applied, so a stale index never answers against newer
data.
_Avoid_: the raw FILE scan (the index is the view, not the ~430 M raw rows), the mounted
database itself

**dbhash**:
NIST's dataset-integrity token for a **Release**: a hash of the final post-delta database,
published per release. A forensic consumer re-verifies any **Lookup Result** against NIST's
published `dbhashes.txt`.
_Avoid_: the file's own digest (that is the Digest being looked up, not the dataset's)

### The lookup

**Known / Unknown**:
Whether the Digest is present in the Hash Set. `Known` = it is a reference data file;
`Unknown` = it is not in the current set. The answer is always scoped to one **Algorithm**
and one Digest — never to a whole file — because the three algorithms are distinct.
_Avoid_: found/missing, match/no-match, "the file is known"

**Invalid**:
A request that names an algorithm nsrllookup does not accept, or carries a value that is
not a well-formed digest for its declared Algorithm. Distinct from Unknown: an Invalid
request was never checked; an Unknown one was checked and absent.

**Lookup Session**:
One `POST /check` request. It carries **one Algorithm** and one or more Digests, and
returns one `Lookup Result` per Digest against the current Hash Set.
_Avoid_: query (when meaning a whole request), "look up this file" (the unit is a Digest, not a file)

**Lookup Result**:
The answer for one Digest at one Algorithm, scoped to the Hash Set that answered it. It
carries full provenance: the digest, its algorithm, the `Known`/`Unknown` status, the
**Set** consulted, the **Release** (date-version), the applied **Delta releases** (ordered),
and the final **dbhash** — enough to re-verify the answer against NIST's published
`dbhashes.txt`.

### The service

**nsrllookup**:
The API service. It receives Lookup Sessions and answers them against its Hash Set. It is
the only thing a consumer talks to. Its lookup interface is **public** (no
authentication); every session is recorded in an **Audit Trail**.

**Audit Entry**:
One record of a completed **Lookup Session**: a timestamp, a caller identifier (a fixed
service id for now), the Algorithm, each digest with its per-item
`Known`/`Unknown`/`Invalid` status, and the **Set**, **Release**, applied **Delta releases**,
and final **dbhash** that answered. The Audit Trail is the forensic guarantee for an open
interface.
_Avoid_: log line, hit (use Audit Entry)

**Provisioner**:
The operator-run, out-of-band step that builds a queryable **Hash Set**: fetch a **Release**
and its ordered **Delta releases**, verify their integrity (zip SHA-1 sidecar, inner SHA-256
signatures, and NIST's **dbhash**), apply the deltas in order, and write the **Hash Set**,
a persisted **Sidecar index**, and a **Provisioning manifest**. It never runs at build or CI
time, and the service never provisions for itself.
_Avoid_: ingester, loader (at boot time, which the service does not do)

**Provisioning manifest**:
The small attestation the **Provisioner** writes alongside the **Hash Set**: the **Set**,
the **Release**, the ordered **Delta releases**, and the integrity values (zip SHA-1, inner
SHA-256 signatures, final **dbhash**). At startup the service is **ready** only when the
manifest is present and its integrity still matches the mounted **Hash Set**.
_Avoid_: a boot-time integrity check (the container trusts the verified mount, not a
recomputed dbhash — see ADR-0006)

**Audit Trail**:
The durable, append-only log of every **Audit Entry** nsrllookup produces. Because the
interface is public, the service is forensically safe by auditing rather than by access
control.

**nsrlsvr**:
The legacy reference-data server and its socket protocol, being retired. Superseded by
nsrllookup's own engine, which queries the Hash Set database directly.
_Avoid_: "the server" (when meaning the replacement engine), nsrlupdate
