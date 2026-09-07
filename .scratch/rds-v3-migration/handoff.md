# Handoff: nsrllookup — migration COMPLETE; `rds-v3-live` rebase effort, tickets 01–05 DONE (5/9), next is 06

two things to know: the **RDS V3 migration is complete and committed**, but it was
built against a **synthetic** on-disk schema. The follow-up effort **`rds-v3-live`**
re-bases the data layer onto NIST's **real** RDS V3 layout and makes the service
deployable. As of this handoff, **tickets `01`–`05` are done**; `05` (the
Provisioner) is landed in the **working tree, NOT yet committed**. `06`–`09`
remain. The suite is green (54 / 98%) and 5 of the spine's tickets are in — not a
dead end. The live spec now exists at `.scratch/rds-v3-live/spec.md` and
`docs/adr/0005..0006` are written.

## 1. Migration status (unchanged, still true)

All tickets `04`–`14` in `.scratch/rds-v3-migration/issues/` are `resolved`.
Tickets `01`–`03` were implemented at `74cf77d`; their `ready-for-agent` bookkeeping
was closed by `b8c5a6c`. Migration commit trail on `main`:
`5274666` → `74cf77d` (01–03) → `e02258a` (04–07 + devcontainer) →
`2a5b904` (08–14) → `786e518` (handoff) → `b8c5a6c` (01–03 bookkeeping).

Service: queries a mounted RDS V3 Minimal **Hash Set** (no `nsrlsvr`), `POST /check`
+ `/health` with full per-Algorithm provenance, append-only **Audit Trail** per
**Lookup Session**, **Delta** at ingest, no retired component.

## 2. WHY a rebase — the migration built on a synthetic schema (UNRESOLVED by 01, now CONFIRMED)

The `rds-v3-live` effort byte-confirmed the real layout in **ticket `01`** (NIST's
shipped `schema.sql`, release `2026.09.1`; evidence + 3 integrity layers in
`.scratch/rds-v3-live/artifacts/`). Confirmed facts (see that ticket's `Answer`):

- **Migration assumed** `METADATA(crc32, md5, md5sha1, sha1, sha256, filename)` —
  **invented**. NIST's real Minimal is a `FILE(sha256, sha1, md5, crc32, file_name,
  file_size, package_id)` table (~441,621,230 rows / 73,778,779 distinct SHA-256 for
  Modern Minimal, per `hash_counts.txt`) plus a `DISTINCT_HASH(sha256,sha1,md5,crc32)`
  **view**. There is **no `METADATA` table, no `md5sha1`, no `filename`** (the column
  is `file_name`); extra columns `file_size`, `package_id`.
- **Deltas are `.sql` files** (`BEGIN TRANSACTION; INSERT/UPDATE/DELETE INTO FILE …`),
  applied in order; Python `sqlite3.executescript` suffices, no CLI.
- **Integrity is 3 layers**: SHA-1 `.zip_sha` sidecar on each zip; SHA-256
  `signatures.txt` inside; NIST **`dbhash`** = the SQLite `dbhash` binary's 40-hex
  output over the final post-delta db, published per release in `dbhashes.txt`
  (`481e5f55f6d1ed63ea0f176779efc5cc5d53e52a` for `RDS_2026.09.1_modern_minimal.db`).
- **No cheap Minimal db**: the only complete real db under ~500 MiB is
   `RDS_2021.12.2_curated.zip` (86.9 MiB, a *curated*, different schema); full Modern
  Minimal is ~18 GiB. Minimal-layout proof comes from the shipped `schema.sql`
   (captured in `01`); mechanics smoke stays on `curated`.

## 3. `rds-v3-live` — DESIGN + PROGRESS

Spec: `.scratch/rds-v3-live/spec.md` (written). ADRs `0005`/`0006` written + committed.
**9 tickets**: `01`, `02`, `03`, `04` **RESOLVED + committed**; `05`
**RESOLVED, in the working tree (uncommitted)**; `06`–`09` `ready-for-agent`.

**Ticket spine (`.scratch/rds-v3-live/issues/`, 9):**
`01` **DONE** `3ba267c` byte-confirm real `FILE`/`DISTINCT_HASH` schema from NIST
`schema.sql` (evidence in `…/artifacts/`) → `02` **DONE** `9509ad0` domain
model + ADR-0005/0006 (`CONTEXT.md` + `docs/adr/0005..0006`) → `03` **DONE** `36c0350`
re-base data layer to `FILE`/`DISTINCT_HASH` + UPPERCASE/case-agnostic Sidecar index
(one red→green batch; `hasheset.py` + every fixture, `40 passed / 98% coverage`) →
`04` **DONE** `131598e` apply a Delta as NIST's ordered `.sql` (copy-on-apply +
`sqlite3.executescript`, no CLI), rebuild Sidecar, refresh provenance, + no-cross-set
guard; `build_delta_sql` is the fixture seam; `hasheset.py` modernised to PEP-8 +
f-strings and is now lint-clean (`42 passed / 98%`) → `05` **DONE (UNCOMMITTED)**
Provisioner + 3-layer integrity in new `api/provision.py` → `06` provisioning
manifest + readiness gate + per-result `dbhash` → fork: `07` real-data mechanics
smoke (one-off on `RDS_2021.12.2_curated`, out of CI, ∥) `08` fixture deploy smoke
(build → run → `/health`+`/check` green, ∥) `09` housekeeping (retire `ticket 15`,
refresh README, `live`-marker already pruned at `d01b933`).
**Next frontier: `06`** (manifest readiness gate + per-result `dbhash`). `07 ∥ 08 ∥ 09`
fork off `06`.

**What landed in `05` (Provisioner, `api/provision.py` — UNCOMMITTED):**
- New Seam-3 module, **no new dependency** (stdlib `hashlib`/`json`/`re`). Three
  integrity verifiers + the ordered apply + the manifest write.
  - **Layer 1** `verify_zip_sha(zip, sidecar)`: zip SHA-1 == NIST `.sha`
     sidecar; tamper/mismatch/unparseable refused.
  - **Layer 2** `verify_signatures(signed_dir, signature)`: every inner file in
     `signatures.txt` (`SHA256(<name>)= <hex>`) hashes to recorded value;
     blank/comment lines skipped, missing/altered refused.
  - **Layer 3** `verify_dbhash(db, published, dbhash)`: final post-delta db's
     token == `dbhashes.txt` value. **`dbhash` injected** (ADR-0006, external
     binary not re-implemented) → assertable on fixtures.
  - `write_manifest`/`read_manifest`: the **Provisioning manifest** (set,
     release, ordered deltas, final `dbhash`) as JSON in the writable data dir;
     the readiness-gate record for `06`.
  - `provision(base, set, release, deltas, published_dbhash, dbhash,
     manifest_path)`: applies each `(release, delta_sql)` **in order** via
     `hasheset.apply_delta` (04), verifies layer 3, writes the manifest;
     **dbhash mismatch refuses** (`ValueError`, writes nothing).
- **Decision log for `05` (grilled, locked):** (a) `dbhash` = **injected token
   function** (not shelling out, binary absent); (b) "fetch" stays an **operator
   step** — the Provisioner verifies+applies **local artifacts**, no download in
    CI; (c) manifest written into `workspace` (operator's writable data dir);
    (d) **this ticket writes the manifest only** — `dbhash` into `dataset()`/
    `/health` + the boot-time manifest **readiness gate** are **`06`**.
- **`pylintrc` change:** `too-many-positional-arguments` added to the existing
   `too-many-*` disable block — it is the pylint-4 successor to the already-
   disabled `too-many-arguments`; `provision()`'s 7-arg signature is the
   orchestrator entry point.
- **Not touched:** `app.py`, `lookup.py`, `hasheset.py` (06 will add the
   `dbhash` field to `dataset()` + the readiness gate). The `dbhash`/`dbhashes.txt`
   `481e5f55…` value and the 3-file `signatures.txt` are captured in
   `.scratch/rds-v3-live/artifacts/extracted/`.

## 4. Gotchas for next session

- **`provision.py` was written clean PEP-8 4-space, and this burned effort this
   session.** The repo's *older* modules (`lookup.py`, `app.py`, `audit.py`, and
   even some test files) use a quirky offset — docstring-opener at `5`, body at `4`
  — that **compiles** but trips a strict 4-space indent check. The Write/Edit tool
   **preserves the bytes you give**, so a new file can be written fully uniform
  4-space (docstrings *and* bodies at 4) and it will compile + lint clean.
   **Gotcha that cost time:** indent-helper literals like `" "` + a 4-wide string
   silently produced 5/11 spaces (the quirk again) until a byte-level check
   (`len(s)-len(s.lstrip(" "))` must be a multiple of 4) caught it. **Rule:** build
   new files with `" " * level` helpers and verify every body line is a multiple of
    4 before writing. `api/provision.py` and `api/tests/test_provision.py` are
    clean 4-space; don't reformat the quirky modules, match their style.
- **CI lint bar (CORRECTED):** CI's `test` job (`.github/workflows/test.yml`) runs
   **`pytest --cov` only — no `pylint`/`flake8` in CI.** `pylint` is a manual,
    in-container check. The repo's own test files don't pass a strict 4-space lint
    (`test_check_health.py` ≈ 4.5/10; existing `W0311` everywhere), so don't
    chase 10/10 on test files — the gate is `pytest`. `app.py` C0303/W1405 and the
    `E0015`/`UserWarning` `pylintrc` quirk are pre-existing.
- **`dbhash` binary is NOT installed locally** (`which dbhash` → not found). Ticket
   `05` handled this by **injecting** the token function (ADR-0006) so layer 3 is
    assertable on a fixture without the binary. Ticket `06` (readiness gate using the
    manifest's recorded `dbhash`) likewise needs no local `dbhash` — the service
   *trusts the mount* (ADR-0006), it does not recompute at boot.
- **Git has NO committed `user.*` config.** Commit with env vars
   (`GIT_AUTHOR_NAME=cybagard`, `GIT_AUTHOR_EMAIL=67512030+cybagard@users.noreply.github.com`,
   `GIT_COMMITTER_*` the same). `git -c user.name=… -m …` **fails** (-c and -m cannot
   combine). `git stash` is safe but **reverts uncommitted work** — prefer
   `git commit` for checkpointing, or `git stash pop`/verify after (it was popped
   cleanly this session). **Commit cadence: one commit per completed tracer bullet.**
- **Indentation quirk (resolved in `hasheset.py` as of `04`):** the original
  `hasheset.py` used a quirky offset (docstring-opener at `5`, body at `4`) that
  **compiles**; mixing levels (opener ≠ body, or a decorator/body mismatch) raises
   `IndentationError: unindent does not match any outer indentation level` — it is
   not a clean "opener==body" rule. Ticket `04` **re-based `hasheset.py` to standard
    PEP-8 4-space indent**, so that file is now clean and lint-free; the Edit tool and
   `Write` preserve exactly the bytes you give, so keep new bodies at one consistent
   4-space level. **Other modules (`lookup.py`, `app.py`, `audit.py`) still use the
   quirky offset** — match their existing style when editing them, don't reformat.
- **NIST S3 facts (CORRECTED, live 2026-09-03):** the flat `RDS/…` objects the prior
   handoff listed are **now `AccessDenied` (403)** for anonymous GET. The working path
   is the **per-release directory** `…/RDS/rds_<release>/`:
   `https://s3.amazonaws.com/rds.nsrl.nist.gov/RDS/rds_2026.09.1/` exposes
   `version.txt`, `README.txt`, `dbhashes.txt`, `hash_counts.txt`, and the zips
   (`RDS_2026.09.1_modern_minimal_delta.zip` + `…_zip_sha`, `…_modern.minimal.zip`,
   etc.), all `public-read` (GET/range `206`). **Probe by exact name inside
   `rds_2026.09.1/`**; bucket **listing** is still `AccessDenied`. The minimal delta
   zip (~185 MiB observed; README says 177 MiB) contains
   `RDS_2026.09.1_modern_minimal.schema.sql`, `signatures.txt`, `readme.txt`, and a
   ~1 GiB `RDS_2026.09.1_modern_minimal_delta.sql`. Current release `2026.09.1`
   (delta-only; last full `2026.03.1`). **The schema/delta are inside the zip**, not
   top-level objects.
- **Capture, don't re-download:** ticket `01`'s evidence is staged in
   `.scratch/rds-v3-live/artifacts/` — `extracted/` holds the 7 small text files
     (committed; `schema.sql`, `signatures.txt`, `delta.readme.txt`, `version.txt`,
     `dbhashes.txt`, `hash_counts.txt`, `README.txt`); `raw/` holds the 185 MiB zip +
      `.zip_sha` (**gitignored** via `artifacts/.gitignore` — kept on disk for tickets
      `05`/`07`, not committed). SHA-1 + SHA-256 of the zip verified against the
      sidecar + `signatures.txt`.
- **`dbhash` binary is NOT installed locally** (`which dbhash` → not found). Ticket
   `05` (integrity layer 3) needs NIST's `dbhash` external binary or a verified
   stand-in — see ADR-0006.
- **Suite / lint / build (run exactly as CI; in-container, dev image `nsrllookup-dev`
   present):**
      test:  docker run --rm -v "$PWD":/workspace -w /workspace/api nsrllookup-dev \
                python -m pytest --cov=api --cov-report=term-missing -q
      build: docker build -t nsrllookup-dev -f .devcontainer/Dockerfile .
      lint:  docker run --rm -v "$PWD":/workspace -w /workspace/api nsrllookup-dev \
                python -m pylint app.py lookup.py hasheset.py audit.py --rcfile=../pylintrc
- **Untracked (never commit):** `.agents/`, `.claude/`, `skills-lock.json`;
   `coverage.xml`/`.coverage` are gitignored.

## 5. Current health + suggested next step

- Suite (in-container, == CI `test` job): **54 passed, 0 skipped, 98% coverage**,
   exit 0.
- Lint: **`provision.py` is 10.00/10, 0 findings** (clean PEP-8 4-space);
    `test_provision.py` ≈ 9.82/10 (two long module-docstring lines only).
     `hasheset.py` still 0 findings. Pre-existing untouched: `app.py` C0303/W1405
     and the `E0015`/`UserWarning` `pylintrc` quirk.
- **`05` is in the working tree, NOT committed** (`api/provision.py`,
    `api/tests/test_provision.py`, the `pylintrc` one-liner, and the
     `.scratch/rds-v3-live/issues/05-*.md` `resolved` state). The standing
     instruction is to **pause after each bullet for confirmation before
      committing** — commit is pending.
- **Next: ticket `06`** — the **readiness gate + per-result `dbhash`**: extend
    `Provenance.dataset()` (and `/health`) to carry the final `dbhash` from the
     manifest, and make the service **ready only when the Provisioning manifest is
     present and its integrity matches the mounted db** (ADR-0005), refusing serve
     on mismatch. The manifest record already exists (`05`); `06` consumes it at
     boot. `07 ∥ 08 ∥ 09` fork off `06`. Commit `05` first (one tracer bullet),
     then `06`.
