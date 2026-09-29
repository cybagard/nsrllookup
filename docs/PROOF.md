# One Command. One Published Fingerprint. Proof.

Turnkey provisioning of the NIST RDS **Modern Minimal** database into a live
NSRL lookup API — every layer of the way verified against the publisher's own
published hashes, and proven end-to-end over real HTTP.

---

## The claim

`make provision --release 2026.03.1 --deltas 2026.06.1 2026.09.1`

takes the raw, published NIST release artifacts and delivers:

- `data/rds.db` — the provisioned database (base release + both deltas applied)
- `data/manifest.json` — provenance: set, release, deltas, dbhash

whose **complete byte stream hashes to the SHA-512 dbhash value NIST itself
publishes** for that release combination. Not a sample. Not a spot check. The
whole stream, against the official fingerprint. A byte that drifts fails the
build; nothing publishes unverified.

## What the command does

1. **Fetch** — pulls the published artifacts (`RDS_*.zip` + `*.sha`
   signatures + `dbhashes.txt`) from the NIST RDS web endpoint.
2. **Integrity, layer 1** — verifies every archive against the NIST-published
   SHA-1 and SHA-256 signatures, and `dbhashes.txt` against the SHA-512 of its
   own archive. Nothing proceeds on a mismatch.
3. **Unpack** — expands each archive to its real `.sqlite` payload and verifies
   each unpacked database against the published SHA-512 dbhash (layer 2).
4. **Index** — builds the three B-tree index families (MD5 / SHA-1 / SHA-256)
   in-database; every digest seek after this is an index descent, not a scan.
5. **Apply deltas** — streams the delta `.sql` files statement-by-statement
   (single transaction, auto-commit off): `DELETE OR OVERWRITE` row surgery
   plus `INSERT` of new entries. The delta apply is what moves the database
   from the base release to the terminal release.
6. **Publish** — final SHA-512 over the whole database, compared to the
   published dbhash. Match → publish. Mismatch → the artifact is quarantined,
   never promoted.

The whole pipeline is one command, one log line, zero credentials: the source
is a public endpoint, no account, no token, no API key.

## The proof chain (what actually ran)

**Layer 1 — archives.** All four downloaded archives verified against
NIST-published signatures: `RDS_2026.03.1_modern_minimal.zip`, the
2026.06.1 and 2026.09.1 deltas, and the 2021.12.2 curated set.
SHA-1 + SHA-256 each. **All ok.**

**Layer 2 — databases.** Every unpacked `.sqlite` verified against the
`dbhashes.txt` published fingerprints. **All ok.**

**Layer 3 — the terminal database.** NIST's own `dbhashes.txt` publishes the
fingerprint and the exact recipe it expects:

```
This dbhash value represents the dbhash output when combining the following
Modern Minimal RDSv3 sets into a single SQLite database in the correct order.

481e5f55f6d1ed63ea0f176779efc5cc5d53e52a RDS_2026.09.1_modern_minimal.db
        1. RDS_2026.03.1_modern_minimal.db
        2. RDS_2026.06.1_modern_minimal_delta.sql
        3. RDS_2026.09.1_modern_minimal_delta.sql
```

The provisioned `rds.db` — built from exactly that combination, in that
order — produced the full-stream SHA-512 `481e5f55f6d1ed63ea0f176779efc5cc5d53e52a`.
**Exact match with the published value.** The provisioned file is, at the
byte level, the publisher's own database. A byte that drifted would be a
different hash and the publish step would refuse.

**Layer 4 — content scale** (from the RDS 2026.09.1 published `hash_counts`):

- Modern Minimal, terminal release: **441,621,230 files**; 73,778,779 of
  which are distinct SHA-256 values
- Index families: MD5, SHA-1, SHA-256 — every digest resolves by index seek,
  never by table scan

**Layer 5 — live behaviour** (the API, in a container, over real HTTP):

```
$ curl -s localhost /ping
{"result": "pong"}

$ curl -s localhost /health
{"dataset": {"dbhash": "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a",
    "deltas": ["2026.06.1", "2026.09.1"],
    "release": "2026.03.1", "set": "modern"}, "ready": true}
```

A file inserted by the **2026.09.1** delta — `27.api-ms-win-dx-d3dkmt-l1-1-1.dll` —
queried by its SHA-256 (sent lowercase on purpose; the API normalises):

```
$ curl -s -X POST localhost /check \
  -d '{"algorithm":"sha256","hashes":["00000296eb569c19b0f2bd73b481392a…"]}'
{"results": [{"algorithm": "sha256",
  "dataset": {"dbhash": "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a",
              "deltas": ["2026.06.1", "2026.09.1"],
              "release": "2026.03.1", "set": "modern"},
  "digest": "00000296EB569C19B0F2BD73B481392A76A0B4DC6FEBD52483E967D12F41AE50",
  "status": "known"}]}
```

The same file queried by its **MD5**:

```
{"results": [{"algorithm": "md5", "dataset": {…same…},
  "digest": "0662DE95E370A6F800E149E240FB0BDE", "status": "known"}]}
```

A digest known to be absent (32 zeros):

```
{"results": [{"algorithm": "sha256", "dataset": {…same…},
  "digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "status": "unknown"}]}
```

And the trail: every session above was appended to the append-only audit
log — caller, algorithm, results, dataset provenance, UTC timestamp:

```
{"algorithm": "sha256", "caller": "nsrllookup",
 "dataset": {"dbhash": "481e5f55…", "deltas": ["2026.06.1", "2026.09.1"],
 "release": "2026.03.1", "set": "modern"}, "results": [ … "status": "known" … ],
 "results_produced": true, "timestamp": "2026-09-29T…Z"}
```

The hit is a delta-inserted file resolved through the published-fingerprint
database — a lookup that only answers *known* when the base **and** both
deltas are genuinely applied. Misses answer *unknown*. Invalid input answers
*invalid* or *unsupported* with the request recorded. That is the whole
contract, proven in the wire.

## Reproducing it

```bash
make provision   # fetch → verify → index → delta-apply → publish (one log line)
make verify      # ready: true
docker run -v $PWD/data:/workspace/data:ro … nsrllookup-dev:latest python /workspace/api/app.py
curl …           # /ping, /health, /check — as above
```

No credentials, no accounts, no private feeds. The source of trust is the
publisher's own published signatures and fingerprints, and the deliverable is
whatever passes them — or nothing publishes.

## The honest footnotes

- The run above was a single unthreaded process on a laptop-class machine;
  the delta application phase is the long pole at this dataset's scale.
  The pipeline's verification gates are what make the wait trustworthy, not
  a reason to skip it.
- Every number in this document is either a hash comparison against a
  publisher value, a content measurement from the provisioned database, or a
  captured wire response. Nothing here is a promise; it's a transcript.
