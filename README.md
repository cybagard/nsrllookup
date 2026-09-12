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
mounted read-only) directly. Its on-disk shape is NIST's real **Set schema**:
a `FILE` table (`sha256, sha1, md5, crc32, file_name, file_size, package_id`)
and a `DISTINCT_HASH` view over it; `crc32` is a physical column but not a lookup
**Algorithm**. Membership is served by a per-Algorithm `hash→known` **Sidecar
index** materialised from that view; the retired `nsrlsvr` daemon and its socket
protocol are gone. See `docs/adr/0001..0006` and
`.scratch/rds-v3-live/spec.md`.

## How it works

- **One service.** A single WSGI app owns the HTTP layer, the lookup module, the
   **Hash Set** access, and the **Audit Trail**. There is no separate server.
- **Mounted volume.** The **Provisioner** produces a queryable **Hash Set** (one
    full **Release** plus any applied **Delta releases**, applied as NIST's ordered
    `.sql`), a persisted **Sidecar index**, and a **Provisioning manifest**, all
    mounted read-only. The Audit Trail is mounted read-write for durability.
- **Proving the mount.** The **Provisioner** verifies integrity in three layers —
    zip **SHA-1** sidecar, inner **SHA-256** `signatures`, and NIST's **dbhash**
    over the final post-delta database — and records all three in the **Provisioning
    manifest**.
- **Readiness gate.** At startup the service is **ready** only when the
    **Provisioning manifest** is present and its integrity values (including the
    final **dbhash**) still match the mounted **Hash Set**; a missing or mismatched
    manifest means **not-ready**, so a stale index never answers against newer data.
    The container trusts the verified mount and does not recompute **dbhash** at boot.
- **Provisioning is one-time.** The **Provisioner** (mount, apply deltas in order,
    verify, write) is an operational step done out of band, never a build or CI step.

## How to use (single service, mounted volume)

1. Provision the **Hash Set** volume out of band: the **Provisioner** fetches NIST's
     Minimal **Set** **Release** and its **Delta releases**, verifies integrity in
     three layers, applies the deltas in order, and writes the **Hash Set**, the
     **Sidecar index**, and the **Provisioning manifest** into the data dir.
2. Start the API against that mounted volume:

    ```shell script
   docker-compose -f docker-compose.prod.yml up -d api
    ```

   The container exposes port 5000. It reports **ready** only once the
    **Provisioning manifest** is present and its integrity matches the mount
    (see the **Readiness gate** above).

Build and test locally with `docker-compose.build.yml` (build the API image and
run the self-contained fixture-based suite — no live server, no real-data
download). A fixture **Hash Set** + manifest boot smoke
(`tests/integration/test_deploy_smoke.py`) drives the whole path —
`/health` **ready** with a **dbhash**-bearing `dataset`, `/check` **known**, and
an empty-volume control that stays **not-ready**.

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
          "deltas": ["2026.06.1"],
          "dbhash": "481e5f55f6d1ed63ea0f176779efc5cc5d53e52a"
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

Reports the loaded **Set** + **Release** + applied **Delta releases** and the
final **dbhash**, plus a `ready` flag. It is **ready** only when the
**Provisioning manifest** is present and its integrity values (zip **SHA-1**,
inner **SHA-256** signatures, final **dbhash**) match the mounted **Hash Set** —
**not-ready** when the manifest is absent or mismatched — so a caller can confirm
provenance and liveness before trusting the answers.

Every **Lookup Session** — successful or rejected — produces one **Audit Entry**
(timestamp, caller, **Algorithm**, each digest + status, and the **Set**,
**Release**, applied **Delta releases**, and final **dbhash** that answered),
appended to the durable **Audit Trail**.
