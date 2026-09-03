# 15: Provision a production RDS V3 Minimal Set (+ Deltas)

**What to build:** the operational step the migration left off a "one-time, out-of-build,
out-of-CI" boundary. Provisioning fetches NIST's **Minimal** **Release** for the served
**Set** (Modern), extracts its RDS V3 SQLite database, applies any **Delta releases** in
order on top of it, and produces the current queryable **Hash Set** that the `prod`
compose mounts read-only. This replaces the retired `svr/prepare-hash-set.sh`
(download + `nsrlupdate`) that ADR-0003 superseded. The lookup machinery already exists
(`provision`, `apply_delta`, `_copy_rows`, `HashSet`, `Provenance`); this wires a real
release + its metadata to it.

**Blocked by:** None (all of 04-14 resolved; builds on `hasheset.provision` /
`apply_delta` / `HashSet`).

**Status:** superseded by `rds-v3-live`

> **Superseded.** This ticket was the production-provisioning ticket opened by the
> "make it live/deployable" pass, before the real NIST schema was confirmed. It is
> **carried forward and replaced** by the `rds-v3-live` effort
> (`.scratch/rds-v3-live/spec.md` + `issues/01..07`), which re-bases the data layer onto
> NIST's **real** `FILE`/`DISTINCT_HASH` layout, adopts `.sql` delta application, and adds
> the three-layer integrity check + provisioning manifest. This `ticket 15`'s "provision a
> production set" goal is now `rds-v3-live` tickets 04–07. Left here as history only.

- [ ] Provisioning fetches + extracts the **Minimal** V3 **Release** for a named **Set**
      (Modern, ~18 GB — not the ~124 GB full set, per ADR-0003) to the mounted db path
      (`./data/rds.db`, consumed read-only by `docker-compose.prod.yml`).
- [ ] **Delta releases** are applied in order onto the current **Release** using the
      existing `apply_delta(base, delta_rows, delta_release)` / `_copy_rows` machinery
      (reading each delta's own V3 db rows), yielding the current **Hash Set**.
- [ ] **Provenance** (**Set**, **Release**, applied **Delta releases**) is derived from
      the downloaded release's own metadata — not hard-coded — so `/health` and every
      **Lookup Result** report the data that answered.
- [ ] The per-Algorithm **hash→known index** (MD5, SHA-1, SHA-256) is built at ingest via
      `provision` / `HashSet`; **CRC-32** is physically present in every row but remains a
      non-supported lookup algorithm.
- [ ] The result mounts read-only at `./data/rds.db` and the service reports
      `{"ready": true, "dataset": {set, release, deltas}}` on `/health`.
- [ ] Provisioning is a one-time / operational step, never a build or CI step (ADR-0003);
      no live-server test and no 18 GB download in CI.
- [ ] A smoke check on a small sample proves fetch → delta → provision → `/health`
      end to end (extend the sample, do not fetch the full set under test).

## Open questions

Scope these before claiming AFK-ready; they are the production story the migration left
deliberately out of scope:

- **Transport + cadence:** how the ~18 GB Minimal set and subsequent quarterly Delta
  releases arrive (one-time pull vs scheduled fetch), and how often deltas are applied.
- **Index-build budget:** `HashSet._build_index`/`known_digests` do a full
  `SELECT <col> FROM METADATA` into a Python `set` per algorithm — on ~940 M rows × 3
  algorithms this is multi-minute and large-RAM. Decide whether the index is rebuilt each
  ingest, or persisted and reloaded.
- **Provenance source of truth:** where the authoritative **Set** / **Release** identifiers
  live in a real V3 db (vs. the current design where `Provenance` is passed in by the
  caller), so the derived provenance is verifiable, not asserted.

## Comments
