# nsrllookup

nsrllookup is a forensic lookup API that answers whether one or more file digests
are **known** reference data files, by checking them against the
**NIST Reference Data Set** (RDS V3, **Modern** **Set**). It is a reference for
separating the benign, pre-existing files in a digital-evidence corpus from the
files of interest — so a lookup is only trustworthy when it reports **which
dataset** answered.

[![Test](https://github.com/cybagard/nsrllookup/actions/workflows/test.yml/badge.svg)](https://github.com/cybagard/nsrllookup/actions/workflows/test.yml)
[![Build & Scan](https://github.com/cybagard/nsrllookup/actions/workflows/build-image.yml/badge.svg)](https://github.com/cybagard/nsrllookup/actions/workflows/build-image.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Why

- **Separate the benign from the interesting.** In a corpus of digital evidence,
  most files are pre-existing reference data. nsrllookup tells you which digests
  are already **Known** so they can be set aside.
- **A reference answers with provenance.** Every answer names the **Set**, the
  **Release**, the applied **Delta releases**, and the final **dbhash** consulted —
  enough for a forensic consumer to re-verify against NIST.
- **Public, but accountable.** The lookup interface is unauthenticated; safety
  comes from a durable, append-only **Audit Trail** that records every session,
  not from a gate. See <a href="docs/adr/0004-public-audited-interface.md">ADR-0004</a>.
- **No daemon, no in-RAM dataset.** One service queries a verified, read-only
  **Hash Set** directly; membership is an indexed on-disk seek.

## What you can rely on

- **Provenanced answers.** Every **Lookup Result** carries the **Set**, the
  **Release** (date-version), the ordered **Delta releases** applied, and the
  final **dbhash** — the token to re-verify against NIST's published
  `dbhashes.txt`.
- **Integrity in three layers.** The **Provisioner** verifies the archive's
  **SHA-1** (NIST's `.sha` sidecar), each inner file's **SHA-256**
  (`signatures.txt`), and NIST's **dbhash** over the final post-delta database,
  and records all three in a **Provisioning manifest**. A layer failure refuses
  the manifest, so an unverified **Hash Set** is never served.
  ([ADR-0005](docs/adr/0005-provisioning-manifest-integrity-token.md),
  [ADR-0006](docs/adr/0006-external-dbhash-trust-the-mount.md))
- **A readiness gate.** At startup the service is **ready** only when the
  **Provisioning manifest** is present and still matches the mounted **Hash Set**;
  a missing or mismatched manifest means **not-ready**, so a stale or unverified
  index never answers.
- **A durable audit.** Every **Lookup Session** — successful or rejected — is
  appended to the **Audit Trail**.

## NSRL coverage

nsrllookup answers against NIST's **Reference Data Set** (RDS V3). Today it
serves one of NIST's four **Sets**:

| **Set**   | Served | Form              |
|-----------|:------:|-------------------|
| **Modern**| yes    | **Minimal** (~18 GB) |
| **Legacy**| no     | — (later work)    |
| **Android**| no    | — (later work)    |
| **iOS**   | no     | — (later work)    |

The **Minimal** form is NIST's compact, de-duplicated archive (the full **Modern**
set is ~124 GB); deltas keep the served **Release** current without re-fetching it.

| **Algorithm** | Lookup |
|---------------|:------:|
| **MD5**       | yes |
| **SHA-1**     | yes |
| **SHA-256**   | yes |
| **CRC-32**    | no — physically present in every row, but a weak checksum, not a supported lookup **Algorithm** |

**Cadence.** NIST publishes quarterly: a full **Release** in March and
**Delta releases** in June, September, and December. A provisioned **Hash Set**
is one **Release** plus whatever **Delta releases** were applied on top of it;
`/health` reports exactly which.

## Quickstart

### Try it — no data, no download

Build the API image and run the self-contained, fixture-based test suite
(including an end-to-end **Hash Set** + **manifest** boot smoke). No live server
and no real-data download:

```shell script
docker-compose -f docker-compose.build.yml up --build api-test
# clean up when done
docker-compose -f docker-compose.build.yml rm -fsv api-test
```

### Run it live — a one-time, ~19 GiB fetch

A fresh box needs a host/volume free for the dataset (the archived base
uncompresses to a ~180 GB database, ~240–256 GiB once the **hash index** is
built; ~260 GiB peak — [ADR-0007](docs/adr/0007-bounded-footprint-turnkey-apply.md)).

1. Provision the **Hash Set** volume out of band:

   ```shell script
   make provision RELEASE=2026.03.1 DELTAS=2026.06.1
   ```

   This fetches the **Minimal** **Set** **Release** and its ordered **Delta
   releases**, verifies all three integrity layers, applies the deltas in order
   (building the per-Algorithm **hash index** into the same `.db`), and writes
   `rds.db` + the **Provisioning manifest** into `./data`.
   `make verify` re-checks a provisioned volume.

   To apply **multiple Deltas**, list them space-separated, **oldest to
   newest** (the example above applies both, so the volume is current at
   `2026.09.1`):

   ```shell script
   make provision RELEASE=2026.03.1 DELTAS="2026.06.1 2026.09.1"
   ```

   The order is meaningful: each Delta's `.sql` applies after the previous one,
   and the **last** Delta is the terminal **Release**, whose NIST-published
   **dbhash** attests the final database (integrity layer 3). List each Delta
   only once.

2. Start the API against that mounted volume (port 5000):

   ```shell script
   docker-compose -f docker-compose.prod.yml up -d api
   ```

3. Confirm provenance, then look digests up:

   ```shell script
   curl -s localhost:5000/health
   curl -s -X POST localhost:5000/check \
        -H 'Content-Type: application/json' \
        -d '{"algorithm": "sha256", "hashes": ["ad7b9c14…"]}'
   ```

## API

### `POST /check`

One request names **one Algorithm** (`md5`, `sha1`, or `sha256`) and one or more
**Digests** of that same algorithm (any letter case, normalised to UPPERCASE).
Each digest yields one **Lookup Result**:

```json
{
  "results": [
    {
      "digest": "AD7B9C14…",
      "algorithm": "sha256",
      "status": "known",
      "dataset": {
        "set": "modern",
        "release": "2026.03.1",
        "deltas": ["2026.06.1"],
        "dbhash": "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
      }
    }
  ]
}
```

- A well-formed request returns **HTTP 200** even when some digests don't parse;
  each unparseable digest comes back as a per-item `invalid`.
- An unsupported **Algorithm** or a malformed body is a request-level rejection
  (**4xx**, no `results` list) and is still recorded as an **Audit Entry**.
- The volume must be **ready** (manifest present and matching); otherwise
  **503** and nothing is served.

### `GET /health`

Reports the loaded **Set** + **Release** + applied **Delta releases** and the
final **dbhash**, plus a `ready` flag. It is **ready** only when the
**Provisioning manifest** is present and its integrity values (zip **SHA-1**,
inner **SHA-256** signatures, final **dbhash**) match the mounted **Hash Set** —
so a caller can confirm provenance and liveness before trusting the answers.

### `GET /ping`

A trivial liveness probe (`{"result": "pong"}`); no **Hash Set** required.

## Configuration

Runtime environment (container; `boot.py`):

| Variable         | Default             | Meaning                              |
|------------------|---------------------|--------------------------------------|
| `RDS_DATA_DIR`   | `/data`             | Mounted **Hash Set** + **manifest** (read-only) |
| `RDS_AUDIT_DIR`  | `/var/log/nsrllookup` | **Audit Trail**, append-only (read-write) |

Provisioner (`make`; overridable):

| Variable  | Default        | Meaning                                  |
|-----------|----------------|------------------------------------------|
| `RELEASE` | `2026.09.1`    | The base **Release** date-version        |
| `DELTAS`  | `2026.06.1 2026.03.1` | Space-separated **Delta releases**, applied in the order listed (oldest → newest) |
| `DATADIR` | `./data`       | Where `rds.db` + **manifest** are written |
| `WORKDIR` | `/tmp/nsrl_provision` | Disposable scratch for the turnkey run |
| `SETNAME` | `modern`       | The **Set** name                         |
| `FAMILY`  | `modern_minimal` | NIST archive family to fetch            |

## How it works

- **One service.** A single WSGI app owns the HTTP layer, the lookup module, the
  **Hash Set** access, and the **Audit Trail** — there is no separate `nsrlsvr`
  daemon.
- **Mounted, read-only volume.** The service opens the provisioned `.db`
  read-only; a per-Algorithm **hash index** lives *inside* that same file, so a
  lookup is an indexed on-disk seek that costs no RAM and keeps no second
  dataset in sync ([ADR-0001](docs/adr/0001-disk-based-v3-engine.md)).
- **Provisioning is one-time.** The **Provisioner** is an out-of-band operator
  step — never a build or CI step ([ADR-0003](docs/adr/0003-migrated-rds-v3-ingestion.md),
  [ADR-0007](docs/adr/0007-bounded-footprint-turnkey-apply.md)); deltas stream and
  apply with bounded memory ([ADR-0008](docs/adr/0008-streaming-delta-sql-scanner.md)).

The decisions behind these choices are documented in [`docs/adr/`](docs/adr/)
(0001–0008) and the API contract lives in the effort specs under `.scratch/`.

## Limitations

- **One Set at a time.** The service serves a single provisioned **Hash Set**
  (one `rds.db` volume). **Legacy**, **Android**, and **iOS** are not served and a
  **Lookup Session** names the one loaded **Set** — this is a **Modern** software
  reference, not a whole-NSRL client.
- **A point-in-time snapshot.** The data is exactly what was applied at provision
  time. The service does not watch NIST or auto-update; a new quarterly
  **Release** or **Delta release** requires the operator to re-provision (see
  **Future work**).
- **A large provision.** Turnkey provisioning of the real **Modern** **Minimal**
  **Set** needs a ~19 GiB download and a volume with roughly 250–260 GiB free
  ([ADR-0007](docs/adr/0007-bounded-footprint-turnkey-apply.md)) — not a
  laptop-class default.
- **Digest-level answers only.** A lookup reports whether a **Digest** is
  **Known** at one **Algorithm** — it does not name the file, its `package_id`, or
  attribute a whole file.
- **One Algorithm per request.** To check one file across **MD5**/**SHA-1**/
  **SHA-256** takes one **Lookup Session** per algorithm; types do not mix.
- **Public, not gated.** The interface has no authentication. Callers are not
  controlled; the service is safe because it **audits** every
  **Lookup Session** ([ADR-0004](docs/adr/0004-public-audited-interface.md)).
- **Self-provisioned.** There is no hosted endpoint; you provision and verify
  your own dataset and run your own instance.

## Development

Work happens in the dev container (`.devcontainer/`, mounted workspace). The
suite is self-contained and fixture-based — no live server, no real-data
download — and runs in CI:

```shell script
docker-compose -f docker-compose.build.yml up --build api-test
```

Code lives under `api/` in three seams: the HTTP layer (`app.py`,
`boot.py`), the lookup module (`lookup.py`, `hasheset.py`), and the
out-of-band **Provisioner** (`provision.py`, `driver.py`).

## Future work

Potential directions, not commitments — each is a deliberate deferral recorded in
the effort specs:

- **The other Sets** — serving **Legacy**, **Android**, and **iOS**; the same
  Minimal **Set** / delta mechanism applies, so it is a bounded extension.
- **Re-sync** — letting an existing volume track a new quarterly **Release** or
  **Delta release** while keeping the **manifest** and **readiness gate** intact,
  so a stale volume goes **not-ready** rather than silently answering.
- **Authentication / caller identity** — an opt-in auth toggle and a
  caller-supplied identity in the **Audit Entry** ([ADR-0004](docs/adr/0004-public-audited-interface.md)).
- **Tamper-evident audit storage** — hash-chaining / WORM hardening of the
  **Audit Trail** beyond durable, append-only.
- **Hosting / scaling** — production deployment, multi-GB transfer automation,
  and the cadence of delta application as a service.

## License

[MIT](LICENSE) © cybagard.
