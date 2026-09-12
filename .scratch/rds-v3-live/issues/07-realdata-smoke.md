# 07: Real-data mechanics smoke (one-off, out of CI)

**What to build:** two one-off, hand-run **real-data** validations that prove the re-based
reader against NIST's actual artifacts. They are **not** added to the automated suite (real
data I/O is multi-GB); they are performed and recorded.

   (a) **Byte-confirm the Minimal schema** from NIST's shipped `schema.sql` (the authoritative
   source for ticket 01; an independent re-check that ticket 03's shape matches NIST).
   (b) **Mechanics smoke** of reader + **delta apply** + **`dbhash`** against a small
    **real** NIST database that exists — `RDS_2021.12.2_curated` (~86.9 MiB). This is a
    *different* (curated) schema, so it is a **mechanics** proof — the `.sql` apply +
    `dbhash` + read path works on a real NIST db — **not** a Minimal-layout proof.

The full ~18 GiB Minimal **Set** and the production deploy remain **operator steps**, out of
this ticket.

**Blocked by:** 06 (manifest/readiness + `dbhash` surfacing) — the mechanics smoke exercises
the reader + delta + readiness + `dbhash` path end to end.

**Status:** ready-for-agent

- [x] (a) The Minimal `FILE`/`DISTINCT_HASH` schema is byte-confirmed against NIST's shipped
          `schema.sql` and recorded.
- [x] (b) The mechanics smoke runs reader + **delta apply** + **`dbhash`** verification
        against `RDS_2021.12.2_curated`, recorded as passing. **PASS** (mechanics; the
        `dbhash` layer exercised via an ADR-0006 stand-in, as this release predates
        `dbhashes.txt` — see `## Answer` (b)).
- [x] Neither validation is added to the automated suite; both are one-off, recorded out of
        CI.

## Answer

### (a) Minimal `FILE`/`DISTINCT_HASH` schema — byte-confirmed from NIST's shipped `schema.sql`

**PASS.** An independent re-check that ticket 03's shape matches NIST, performed against the
authoritative artifact staged in `.scratch/rds-v3-live/artifacts/` (the ~206 MiB
`RDS_2026.09.1_modern_minimal_delta.zip`, which ships `schema.sql`). Release **2026.09.1**.

Full 3-layer integrity of the source artifact, re-run at `2026-09-12` (not just cited from 01):

- **Layer 1 (transport):** `shasum -a 1 raw/RDS_2026.09.1_modern_minimal_delta.zip` =
   `fc23ae7332b9188a089baf8fb53b9a6b463701d5`, **== the shipped `…_zip.sha` sidecar**.
- **Layer 2 (contents, all three inner files == `signatures.txt`):**
   `sha256(RDS_2026.09.1_modern_minimal_delta.sql)=4a2079605dea982265fa7684990553d9a77077c5e199ed69163937d18e034050`;
   `sha256(RDS_2026.09.1_modern_minimal.schema.sql)=b37a8c53dcc81a00828f7e53177b1c38c90dde8dee83a012d5ec56a8cc24ca72`;
   `sha256(readme.txt)=b42a0e7ae3fc623fd140a9534a9bc938e9cdedf6820b1a8e30dbe4b7e64251cb`.
- **Artifact identity:** `sha256(extracted/schema.sql)=b37a8c53…ca72`, **1519 bytes**,
   **byte-identical** to the `schema.sql` streamed out of the zip (`diff` clean).
   `extracted/schema.sql` **is** NIST's authoritative schema.

Against that `schema.sql`, ticket 03's re-based shape in `api/hasheset.py` matches
byte-for-byte:

| Element | NIST `schema.sql` | ticket 03 `hasheset.py` | Match |
| --- | --- | --- | --- |
| `FILE` columns | `sha256, sha1, md5, crc32, file_name, file_size, package_id` | `COLUMNS` (7) | yes |
| `DISTINCT_HASH` view | `SELECT DISTINCT sha256, sha1, md5, crc32 FROM FILE` | `DISTINCT_HASH_VIEW` | yes |
| `crc32` | physical column | `CRC32_COLUMN`, not an `Algorithm` | yes |
| `METADATA` table | **absent** | absent | yes (refuted) |
| `md5sha1` col | **absent** | absent | yes (refuted) |
| `filename` col | **absent** (it is `file_name`) | `file_name` | yes (refuted) |

The real schema also ships `MFG`, `OS`, `PKG`, `VERSION` tables (not consulted by lookup);
`FILE.package_id` is an FK into `PKG`. This is an out-of-CI, one-off confirmation recorded
here — **not** added to the automated suite (per the ticket and the spec's Testing
Decisions). Checkbox (a) is therefore closed.

### (b) Mechanics smoke of reader + delta apply + `dbhash` — PASS (out of CI)

**PASS.** Ran against `RDS_2021.12.2_curated` — a real NIST db that exists
(~86.9 MiB, 279 MiB uncompressed). It is a *different*, **older** schema, which is
the point of the mechanics proof:

- **Schema is genuinely different (confirms "mechanics, not Minimal proof").**
   `RDS_2021.12.2_curated.schema.sql` ships the **`METADATA` table** (with
   `crc32, md5, sha1, sha256` columns + `package_object`/`application`/`os`/
   `language` relations) and a **6-column `FILE` view**
   (`sha256, sha1, md5, file_name, file_size, package_id`) — **no `DISTINCT_HASH`
   view, no `crc32` in `FILE`**. That is the very `METADATA`/pre-Minimal layout the
   migration refuted for the current Minimal set, so reading it proves the mechanics
   on a real NIST db **without** pretending the curated schema equals Minimal's.
   `677,723` `METADATA` rows, `408,811` distinct SHA-256.
- **The reader seam adapts to the layout, not the reverse.** The only change the
   reader needs for this layout is the one the ticket 03 design anticipated: where
   Minimal ships a `DISTINCT_HASH` view, the curated db materialises a DISTINCT
   `SELECT DISTINCT sha256, sha1, md5 FROM FILE` view instead. The per-algorithm
   index build (`known_digests`/`HashSet`) and the lookup path are unchanged.

**Integrity (layers 1–2, real; layer 3 exercised via ADR-0006 stand-in).**
`RDS_2021.12.2_curated.zip` (87,000,867 B) downloaded from
`https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/rds_2021.12.2/RDS_2021.12.2_curated.zip`
(the per-release path; the flat `…/RDS/RDS_2021.12.2_curated.zip` 403s).

- **Layer 1 (transport):** `sha1(zip)=8d2dd3cb654c9a6978a37852b6f71626237fc674`,
   **== the shipped `…_curated.zip.sha` sidecar**.
- **Layer 2 (contents):** this release predates the inner SHA-256 convention — its
   `signatures.txt` carries **SHA-1** hashes. All three match:
   `sha1(RDS_2021.12.2_curated.db)=3f2c1f015f8f7dc85e5feda56b1feae88bc323cb`;
   `sha1(…schema.sql)=c6f0225f0c8809d0df22587f9be128f54374ce03`;
   `sha1(readme.txt)=8a632d50f6fd023ac684e24db1dd497b65eb7ac7`.
- **Layer 3 (dataset `dbhash`):** **exercised, not NIST-verified.** `dbhash` is
   NIST's external binary (ADR-0006 — not re-implemented, not installed locally), and
   this 2021 release predates the `dbhashes.txt` convention, so there is **no
   NIST-published token to check against**. The `verify_dbhash` *mechanic* is proven
   (accepts the matching token, refuses a mismatch) using a self-computed stand-in;
   a real NIST-token check for this release is not possible this session and is the
   one open strand. A release that *does* publish a token (e.g. 2026.09.1,
   `481e5f55…`) would close it via `provision.provision(…, published_dbhash, dbhash)`.

**Mechanics result — all pass** (`.scratch/rds-v3-live/artifacts/realdata_smoke.py`,
one-off, out of CI; not added to the automated suite):

| Check | Result |
| --- | --- |
| reader materialises a distinct-sha256 index over the real db | **408,811** distinct (= README) |
| a real digest is `known`; an absent one is `unknown` | pass |
| membership is case-agnostic (lowercase resolves) | pass |
| lookup per-result path yields known + unknown w/ provenance | pass |
| delta apply (NIST-style `.sql` via `executescript`) makes the new digest known | pass |
| base db untouched by copy-on-apply; provenance carries the ordered delta | pass |
| `verify_dbhash` accepts matching token / refuses mismatch | pass |

The scripted delta was a NIST-style `.sql` (`BEGIN TRANSACTION;
INSERT INTO METADATA (…) VALUES (…); COMMIT`) into the **curated `METADATA` table**
(projected by the `FILE` view) — exercising ticket 04's `executescript` apply, not
the Minimal `FILE` column set.

This is an out-of-CI, one-off record, **not** added to the automated suite (real
data I/O is multi-GB), per the ticket and the spec's Testing Decisions.
