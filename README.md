# nsrllookup

nsrllookup is a Web API built with Python and Flask. It answers whether one or
more file digests are **known** reference data files, by checking them against
the NIST Reference Data Set. It is a forensic reference for separating the
benign, pre-existing files in a digital-evidence corpus from the files of
interest, so a lookup is only trustworthy when it reports **which dataset**
answered.

The lookup interface is **public** (no authentication); every **Lookup Session**
is recorded in a durable, append-only **Audit Trail** instead of being gated.

| Service | main |
|---------|------|
| Quality | [![Codacy Badge](https://app.codacy.com/project/badge/Grade/f5b1705369794e52b5b46ec11261d46d)](https://app.codacy.com/gh/cybagard/nsrllookup/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=cybagard/nsrllookup&amp;utm_campaign=Badge_Grade) |
| API     | ![Docker Pulls](https://img.shields.io/docker/pulls/cybagard/nsrllookup-api) |
|         | ![Docker Cloud Build Status](https://img.shields.io/docker/cloud/build/cybagard/nsrllookup-api) |

The engine queries NIST's RDS **V3** Minimal **Set** (a SQLite **Hash Set**,
mounted read-only) directly with a per-Algorithm `hash→known` index built at
ingest; the retired `nsrlsvr` daemon and its socket protocol are gone. See
`docs/adr/0001..0004` and `.scratch/rds-v3-migration/spec.md`.

## How it works

- **One service.** A single WSGI app owns the HTTP layer, the lookup module, the
   **Hash Set** access, and the **Audit Trail**. There is no separate server.
- **Mounted volume.** Provisioning produces a queryable **Hash Set** (one full
   **Release** plus any applied **Delta releases**) and a recorded **Provenance**
   (the **Set**, the **Release** date-version, the applied **Delta releases**),
   mounted read-only. The Audit Trail is mounted read-write for durability.
- **Ingest is one-time.** Provisioning (mount + apply deltas) is an operational
   step done out of band, never a build or CI step.

## How to use (single service, mounted volume)

1. Provision the **Hash Set** volume out of band (mount NIST's Minimal **Set**
       and apply any **Delta releases**).
2. Start the API against the mounted volume:

   ```shell script
   docker-compose -f docker-compose.prod.yml up -d api
   ```

   The container exposes port 5000.

Build and test locally with `docker-compose.build.yml` (build the API image and
run the self-contained fixture-based suite — no live server).

## API

### `POST /check`

One request names **one Algorithm** (`md5`, `sha1`, or `sha256`) and one or more
**Digests** of that same algorithm (any letter case, normalised to UPPERCASE).
Each digest yields one **Lookup Result**:

```json
{
  "results": [
    {
      "digest": "AD7B9C14...",
      "algorithm": "sha256",
      "status": "known",
      "dataset": {
        "set": "modern",
        "release": "2026.03.1",
        "deltas": ["2026.06.1"]
      }
    }
  ]
}
```

- A well-formed request returns **HTTP 200** even when some digests don't
      parse; each unparseable digest is a per-item `invalid`.
- An unsupported **Algorithm** or a malformed body is a request-level rejection
   (**4xx**, no `results` list) and is still recorded as an **Audit Entry**.
- **CRC-32** is physically present in every row but is **not** a supported
      lookup algorithm.

### `GET /health`

Reports the loaded **Release** + applied **Delta releases** and a `ready` flag
(not-ready when no **Hash Set** is provisioned), so a caller can confirm
provenance and liveness before trusting the answers.

Every **Lookup Session** — successful or rejected — produces one **Audit Entry**
(timestamp, caller, **Algorithm**, each digest + status, and the **Release** +
deltas that answered), appended to the durable **Audit Trail**.
