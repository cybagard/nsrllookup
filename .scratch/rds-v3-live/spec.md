# Spec: Re-base nsrllookup onto NIST's real RDS V3 layout (the `rds-v3-live` effort)

Status: ready-for-agent

This spec materialises the design agreed (grilled) in the prior session and captured in
`.scratch/rds-v3-migration/handoff.md` §3. It re-bases the data layer onto NIST's
**real** RDS V3 on-disk layout, makes the service **deployable** against a real mounted
**Hash Set**, and introduces integrity + a readiness gate. It uses the vocabulary of
`CONTEXT.md` and respects ADR-0001..0004; it will open **ADR-0005** (the provisioning
manifest as the integrity token / readiness gate) and **ADR-0006** (accepting NIST's
external `dbhash` dependency, trusting the verified mount). The prior `rds-v3-migration`
effort is complete and committed; this effort does not re-litigate it.

## Problem Statement

nsrllookup looks deployable, but its data layer is calibrated to a **synthetic** on-disk
schema that NIST does not publish. Ticket `04` of the migration "confirmed" a
`METADATA(crc32, md5, md5sha1, sha1, sha256)` layout with `md5sha1`; NIST's **real**
Minimal **Set** is a `FILE` table that has **no `METADATA` table and no `md5sha1`**. So
the service **cannot open a real Hash Set** — a `known`/`unknown` answer it produces
today is validated only against an in-repo fixture that no real release ever had. For a
**forensic** reference, that is not a cosmetic gap: an answer that is checked against the
wrong data model is untrustworthy, and the only thing that currently makes a "live"
service trustworthy is the **audit record**, not the **dataset** it checked.

Secondary problems the same pass surfaced:

- **Deltas are mis-modeled.** The migration applies a **Delta** as merged Python row-dicts;
  NIST publishes a delta as a `.sql` of `INSERT/UPDATE/DELETE` run against the base db.
- **No integrity guarantee.** A mounted, pre-produced **Hash Set** is never checked against
  NIST's published integrity values at ingest, and nothing at boot can *prove* the mounted
  data is the dataset NIST published.
- **No turnkey provisioning.** `docker-compose.prod.yml` mounts `./data/rds.db` read-only
  but nothing produces that volume; an operator cannot bring a fresh box to a trusted
   "ready" state.

## Solution

Re-base the engine onto NIST's real layout, make provisioning turnkey, and gate readiness
on a verified-integrity attestation — keeping the service public + audited.

- **Real layout.** The data layer reads a `FILE(sha256, sha1, md5, crc32, file_name,
   file_size, package_id)` table with a `DISTINCT_HASH(sha256,sha1,md5,crc32)` **view**
   that NIST ships. Lookups become **case-agnostic**: digests are normalised to
   **UPPERCASE** (matching NIST's uppercase presentation, and the existing lookup
  normalisation), and a **per-Algorithm hash→known index** is built by **materialising
   `DISTINCT_HASH`** (the ~72M distinct digests) rather than scanning the ~432M raw
   `FILE` rows.
- **Real deltas.** A **Delta release** is a `.sql` file applied to the base **Hash Set**
  via SQLite's execute-script (the `.read` mechanism, no external CLI), which then
   **rebuilds the index** and refreshes **Provenance**.
- **Turnkey, out-of-band provisioning.** A **Provisioner** (a one-time, operator-run step,
   never a build/CI step) fetches a **Release** + its **Delta releases**, **verifies
   integrity in three layers** (zip **SHA-1** sidecar, inner **SHA-256** `signatures`, and
   NIST's **`dbhash`** over the final db), applies the deltas in order, and writes the
   queryable **Hash Set**, a persisted **sidecar index**, and a **Provisioning manifest**.
- **Readiness gate.** The container reads the **Provisioning manifest** at startup and
   reports **`ready`** only when the manifest is present **and its integrity values match
   the mounted db**. The persisted index stores the **dbhash + Release** it was built from
   and **refuses to serve on mismatch**.
- **Traceable answers.** Each **Lookup Result**'s `dataset` block carries the **Set**,
   **Release**, ordered **Delta releases**, and the **final `dbhash`**, so a forensic
   consumer can re-verify any answer against NIST's `dbhashes.txt`.
- **Trust the mount.** The container is a pure read-only consumer of the **verified data
   dir**; it does not run `dbhash` itself. Integrity is established once, at provisioning.
- **Access model unchanged.** The interface stays **public + audited** (no auth).

## User Stories

1. As a forensic investigator, I want a `known`/`unknown` answer to be checked against NIST's
   **real** Minimal **Set**, so that the answer reflects the dataset NIST actually
   published, not a fixture only this repo knew about.
2. As a forensic investigator, I want a lookup by **MD5**, **SHA-1**, and **SHA-256** to
   all resolve against the real **Set**, so that the three algorithms remain first-class.
3. As a forensic investigator, I want a digest submitted in any letter case to resolve
   identically, so that I do not have to pre-normalise case, and a lowercase-stored NIST
   digest is still found.
4. As a forensic investigator, I want `crc32` — physically present in every row — to be
   physically present but **not** accepted as a lookup **Algorithm**, so that a weak
   checksum never stands in for a real digest.
5. As a forensic investigator, I want one **Lookup Result** per submitted **Digest**, each
   carrying its own per-**Algorithm** **Known/Unknown/Invalid** status, so that "known
   under MD5" is never conflated with "known under SHA-256."
6. As a forensic investigator, I want each **Lookup Result** to name the **Set**, the
   **Release**, the applied **Delta releases**, and the **final `dbhash`**, so that my
   report is traceable to the exact, verified dataset that answered it.
7. As a forensic investigator, I want to re-verify any historical answer against NIST's
   published `dbhashes.txt`, so that an answer I recorded earlier can be re-validated.
8. As an operator, I want a turnkey way to provision a fresh box — fetch a **Release** +
   **Delta releases**, verify integrity, apply deltas, and write the queryable **Hash Set**
   + **sidecar index** + **Provisioning manifest** — so that bringing the service to a
   trusted "ready" state is a single, scripted step.
9. As an operator, I want provisioning to **verify integrity in three layers** (zip
   **SHA-1**, inner **SHA-256** signatures, NIST **`dbhash`**), so that I can trust the
   volume before the service answers against it.
10. As an operator, I want **Delta releases** applied **in order** onto the current full
    **Release**, so that the **Hash Set** stays the most current NIST publishes without a
    full re-download.
11. As an operator, I want provisioning to be a **one-time, out-of-band** step that is
    **never part of a build or CI**, so that a multi-gigabyte dataset does not transit a
    pipeline.
12. As an operator, I want the service to report **not-ready** when no **Provisioning
    manifest** is present, so that I do not serve answers against an unverified or empty
    volume.
13. As an operator, I want the service to refuse to serve a persisted **index** whose
    recorded **dbhash/Release** no longer matches the mounted **Hash Set**, so that a
    stale index never answers against newer data.
14. As an operator, I want a **Deploy smoke** (build → run → `/health` + `/check` green)
    on a **fixture**, so that the deploy path is proven this session without a multi-gigabyte
    download.
15. As a security reviewer, I want every **Lookup Session** — successful or rejected — to
    produce an **Audit Entry**, so that the public interface stays forensically accountable.
16. As a maintainer, I want the data layer, **Delta** apply, and provisioning expressed
    through their existing seams (data layer, lookup module, HTTP layer) plus a single new
    **Provisioner** seam, so that the change is concentrated and testable.
17. As a maintainer, I want the **Domain model** updated so that the real **Set schema**,
    the **Sidecar index**, the **Provisioner/Provisioning manifest**, the **`dbhash`**, and
    the sharpened **Delta release** are recorded, so the codebase's vocabulary matches
    reality.
18. As a downstream integrator, I want the **Lookup Result** `dataset` block contract to be
    stable and explicit, so that I can code against its fields with confidence.
19. As an operator validating against real data, I want a **real-data mechanics smoke**
    (reader + delta + `dbhash`) against a small real NIST database that exists, so that the
    mechanics are proven on real artifacts.
20. As an operator, I want the full ~18 GiB Minimal **Set** and the production
    deployment to remain an **operator step**, so that a design/validation session is never
    blocked by a 18 GiB download.

## Implementation Decisions

**Schema re-base (respects CONTEXT.md `Algorithm`/`Digest`; supersedes ticket 04's claim).**
- The data layer is re-based from the synthetic `METADATA(crc32, md5, md5sha1, sha1,
   sha256, filename)` to NIST's real **Minimal** layout: a `FILE` table with
   `sha256, sha1, md5, crc32, file_name, file_size, package_id`, and a
   `DISTINCT_HASH(sha256, sha1, md5, crc32)` **view** that NIST ships. There is **no
   `md5sha1`** column; the filename column is `file_name`. **`crc32`** is physically
   present in every row but is **not** a supported lookup **Algorithm** (unchanged from the
   domain model).
- **Digest casing** is normalised to **UPPERCASE** on both the sidecar index build and the
   input digest, so membership is case-agnostic (NIST's presentation is uppercase; this also
   matches the existing lookup normalisation).
- **Membership** is served by a **per-Algorithm hash→known index** — the **Sidecar index** —
   built by **materialising the `DISTINCT_HASH` view** (the ~72M distinct digests), not by
   scanning the ~432M raw `FILE` rows.

**Delta application (respects ADR-0003).**
- A **Delta release** is NIST's `.sql` file (`BEGIN TRANSACTION; INSERT/UPDATE/DELETE INTO
  …`) applied to the base **Hash Set** via SQLite's execute-script — the documented `.read`
   mechanism — with **no external CLI** required (Python's `sqlite3` executescript suffices).
   **Minimal** deltas apply only to **Minimal** bases.
- Applying a **Delta** **rebuilds the Sidecar index** and **refreshes Provenance** (the
   **Release** + the now-applied, ordered **Delta releases**). Tests model a **Delta** as
   a set of inserts against a small sample db.

**Integrity, three layers (new; grounds the new ADR-0006).**
- **Layer 1 — transport:** the **SHA-1** value from each object's `.sha` sidecar matches
   the fetched zip.
- **Layer 2 — contents:** the **SHA-256** values in the inner `signatures.txt` match the
   shipped delta/schema component files.
- **Layer 3 — dataset:** NIST's **`dbhash`** — the output of the SQLite `dbhash` program
   over the **final post-delta** database — matches the value NIST publishes in
   `dbhashes.txt` for that **Release**. `dbhash` is accepted as a **provisioning-time
   external dependency** (per ADR-0006): its bit-level algorithm is **verified against
   NIST's published `dbhashes.txt`**, not re-implemented. **`dbhash`** is a new domain term:
   NIST's dataset-integrity token for a **Release**.
- The **container trusts the verified data dir** and does **not** run `dbhash` at boot
   (ADR-0006); integrity is established once, at provisioning.

**Readiness gate + Provenance surfacing (new; grounds the new ADR-0005).**
- A **Provisioning manifest** (a small record in the writable data dir) captures the **Set**,
   the **Release**, the **ordered Delta releases**, and the **three integrity values**.
- At startup the container reads the manifest and reports **`ready`** **iff the manifest is
   present AND its integrity values match the mounted db**. **`Provisioning manifest`** and
   **`Provisioner`** are new domain terms.
- The persisted **Sidecar index** stores the **dbhash + Release** it was built from and
   **refuses to serve on mismatch**, rebuilding only when a **Delta** is applied.
- Each **Lookup Result**'s `dataset` block carries **`set`, `release`, ordered `deltas`,
   and the final `dbhash`** — the minimal set needed to re-verify an answer against
   `dbhashes.txt` without response bloat. The **full triple** (sha1 sidecar, sha256
   signatures) and the **ordered per-delta `dbhash` chain** live in the **manifest /
   `/health`**, not repeated per result. **Provenance** is extended to carry `dbhash`.

**Provisioner (turnkey).**
- The **Provisioner** is a wizard-driven, operator-run flow (`make provision` / `make
   verify`): **fetch → verify (3 layers) → apply deltas in order → write the queryable
   Hash Set + Sidecar index + Provisioning manifest**. It is a **one-time, out-of-band**
   step; the container itself is a **pure read-only consumer** with no boot-time ingest
   (respects ADR-0003). Interactive/one-off bits use the **wizard** skill; mechanical bits
   are scripted.

**Access model (respects ADR-0004).**
- The interface stays **public + audited**. No authentication, no token. A **caller-supplied
   identity** in the **Audit Entry** (vs the current fixed service id) and an **auth
   toggle** are later, separate tickets — out of scope here.

**Domain model (single context ⇒ root `CONTEXT.md`).**
- `CONTEXT.md` gains/sharpens: the real **Set schema** (`FILE`/`DISTINCT_HASH`, `crc32` a
   column), **Sidecar index**, **Provisioner** + **Provisioning manifest**, **`dbhash`**,
   and **Delta release** sharpened to "a `.sql` of INSERT/UPDATE/DELETE applied in order."
   `CONTEXT.md` stays implementation-free (glossary only).
- **ADR-0005** (manifest = integrity token / readiness gate) and **ADR-0006** (external
   `dbhash` dependency / trust-the-mount) are created for the two hard-to-reverse,
   surprising, real-trade-off decisions.

## Testing Decisions

**What a good test is here.** Tests assert **external behaviour at a seam**, not SQL or
index internals. The behaviour under test is the mapping from a request (Digest, Algorithm,
Hash Set) to a **Lookup Result** (+ its **Audit Entry** side effect), and — for the
data/provision side — *smoke checks* that a real-layout db is queryable, that a delta
applies, that integrity verifies, and that readiness gates correctly. Real-data
I/O is verified by **smoke**, not by unit/behaviour assertions.

**Seams (prefer existing; add one new).**
- **Seam 1 — the API boundary (existing).** Drive `POST /check` + `/health` through the
   WSGI/HTTP test client. Assert per-item `known/unknown/invalid`; 200-with-per-item-
   `invalid` vs 4xx-on-bad-`Algorithm`/malformed-body; the `dataset` block now also carries
   `dbhash`; **not-ready** when no manifest is present; the **Audit Entry** is produced as
   an observed effect.
- **Seam 2 — the lookup module (existing).** `look_up(hash_set, digests, algorithm) ->
   [Lookup Result]` against a **real-layout fixture Hash Set** (a small `FILE` table). This
   is the cheap assertion point for MD5/SHA-1/SHA-256 equivalence, case-insensitivity,
   SHA-256 dedup → one `known`, and `crc32` rejected — all now against a fixture built in
   NIST's **real** shape, not the synthetic one.
- **Seam 3 — the Provisioner / data side (new, I/O-bound).** Verified by **smoke** only:
   a small real-layout db is provisioned, a delta **applies and rebuilds the index**,
   integrity **verifies** (against a self-computed `dbhash`/sha for the fixture), the
   **manifest** drives `ready`, and **mismatch → not-ready / refuses-serve**. This side
   (multi-GB real data) is **never a unit/behaviour test**.
- **One-off, out-of-CI, real-data validations** are run by hand and recorded, **not**
   added to the suite: (a) byte-confirm the Minimal `FILE`/`DISTINCT_HASH` schema from
   NIST's shipped `schema.sql`; (b) a mechanics smoke of reader + delta + `dbhash` against
   a small **real** NIST database (`RDS_2021.12.2_curated`, ~86.9 MiB — a *different*,
   curated schema, so a **mechanics** proof, not a Minimal-layout proof). The full ~18 GiB
   Minimal + the production deploy stay **operator steps**.
- **Deploy smoke (this session, fixture-based):** build the image → run it → `/health`
   reports `ready` and `/check` returns a `known` against the fixture **Hash Set**.
- **Prior art.** `test_hasheset_layout.py` (the data-layer smoke) and
   `test_end_to_end.py` (provision → delta → all algorithms → audit → retired-route 404) are
   the successors: the layout smoke is re-pointed at the **real** `FILE`/`DISTINCT_HASH`
   shape, and the end-to-end smoke gains the manifest/readiness + `dbhash` assertions.
   Fixtures that previously used the synthetic columns (`crc32`/`md5sha1`/`filename`) are
   re-built in the real shape.

## Out of Scope

- **Authentication / caller identity.** The interface stays public; an **auth toggle** and a
   **caller-supplied identity** in the **Audit Entry** are later tickets (ADR-0004).
- **The Legacy, Android, and iOS Sets.** Only the **Modern** **Set** is in scope; the
   Minimal/delta mechanism is the same, selecting other Sets is later.
- **Tamper-evident audit storage.** The **Audit Trail** stays durable + append-only;
   hash-chaining/WORM hardening is not in scope.
- **`crc32` as a lookup.** Present as a column, not a supported **Algorithm**.
- **Mixing digest types within one request.** One **Algorithm** per **Lookup Session**.
- **Full ~18 GiB Minimal download / production deployment** in this session. They are
   operator steps; the deploy smoke is fixture-based and real-data checks are one-off.
- **Re-implementing `dbhash`.** It is used as NIST's external binary, verified against
   `dbhashes.txt` (ADR-0006).
- **Scheduling / multi-GB transport automation** (cadence of delta application, large-file
   transfer engineering) — operational follow-ups beyond this effort.
- **The `rds-v3-migration` effort itself.** Complete and committed; this effort only
   supersedes its data-layout claim (ticket 04) and retires its superseded `ticket 15`.

## Further Notes

- **`dbhash` is the integrity token.** Because the interface is open, every answer and every
   request is only trustworthy through a verified dataset identity. Provenance is extended
   with `dbhash`; the `dataset` block's job is "does this help a forensic consumer know
   exactly what answered, and was it verified."
- **Real-data reality (live, captured during design):** NIST distributes RDS V3 from
   `https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/` (**not** `nist.gov`, whose download
   URL 403s). Bucket **listing is access-denied** but individual objects are **public-read**,
   so probe by exact name. Real, relevant objects: `RDS_2026.03.1_modern_minimal.zip`
   (~18 GiB), `..._modern_minimal_delta.zip` (~206 MiB — contains `schema.sql` +
   `signatures.txt` + `..._delta.sql` + `readme.txt`), `RDS_2021.12.2_curated.zip` (86.9 MiB,
   a *curated* db). Current **Release** `2026.09.1` is delta-only (last full `2026.03.1`).
   Per-release `version.txt`/`dbhashes.txt`/`hash_counts.txt`/`README.txt` are live.
- **Supersession.** Ticket `04` "confirmed" a layout that does not match NIST; `ticket 15`
   (the earlier production-provisioning ticket) is **retired** by this effort. The
   `live`-marker prune already in the working tree is an independent, harmless cleanup, kept.
- **Vocabulary.** This spec uses the terms of `CONTEXT.md` plus the additions above; any new
   term is written into `CONTEXT.md` when the relevant ticket lands.
