# Handoff: nsrllookup — migration COMPLETE; `rds-v3-live` rebase effort, tickets 01–04 DONE (4/9), next is 05

two things to know: the **RDS V3 migration is complete and committed**, but it was
built against a **synthetic** on-disk schema. The follow-up effort **`rds-v3-live`**
re-bases the data layer onto NIST's **real** RDS V3 layout and makes the service
deployable. As of this handoff, **tickets `01`–`04` are done and committed**;
`05`–`09` remain. The suite is green and 4 of the spine's tickets are landed — not a
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
**9 tickets**: `01`, `02`, `03`, `04` **RESOLVED + committed**; `05`–`09`
`ready-for-agent`.

**Ticket spine (`.scratch/rds-v3-live/issues/`, 9):**
`01` **DONE** `3ba267c` byte-confirm real `FILE`/`DISTINCT_HASH` schema from NIST
`schema.sql` (evidence in `…/artifacts/extracted/`) → `02` **DONE** `9509ad0` domain
model + ADR-0005/0006 (`CONTEXT.md` + `docs/adr/0005..0006`) → `03` **DONE** `36c0350`
re-base data layer to `FILE`/`DISTINCT_HASH` + UPPERCASE/case-agnostic Sidecar index
(one red→green batch; `hasheset.py` + every fixture, `40 passed / 98% coverage`) →
`04` **DONE** `131598e` apply a Delta as NIST's ordered `.sql` (copy-on-apply +
`sqlite3.executescript`, no CLI), rebuild Sidecar, refresh provenance, + no-cross-set
guard; `build_delta_sql` is the fixture seam; `hasheset.py` modernised to PEP-8 +
f-strings and is now lint-clean (`42 passed / 98%`) → `05` Provisioner (3-layer
integrity; wizard-driven `make provision`/`verify`) → `06` provisioning manifest +
readiness gate + per-result `dbhash` → fork: `07` real-data mechanics smoke (one-off on
`RDS_2021.12.2_curated`, out of CI, ∥) `08` fixture deploy smoke (build → run →
`/health`+`/check` green, ∥) `09` housekeeping (retire `ticket 15`, refresh README,
`live`-marker already pruned at `d01b933`).
**Next frontier: `05`** (Provisioner + 3-layer integrity). `07 ∥ 08 ∥ 09` fork off
`06`.

**What landed in `03`+`04` (data layer, `api/hasheset.py`):**
- `TABLE = "FILE"`, `COLUMNS = (sha256, sha1, md5, crc32, file_name, file_size,
  package_id)`; `DISTINCT_HASH_VIEW = "DISTINCT_HASH"` built by
   `build_minimal_fixture_db`; the index materialises the view (UPPERCASED);
   `is_known` UPPERCASES the input → case-agnostic. `crc32` present, not a lookup
   Algorithm. Synthetic `METADATA`/`md5sha1`/`filename` gone.
- **`04` did the delta mechanism (this was left from `03`):** `apply_delta(base,
  delta_sql, delta_release, set_name=None)` now runs NIST's ordered `.sql` against a
   **copy** of the base via `sqlite3.executescript` (the `.read` mechanism, no CLI)
   then rebuilds the Sidecar + refreshes provenance (deduped). No cross-set
   application: a `set_name` ≠ base's is refused (`ValueError`). `build_delta_sql(rows)`
   renders a Delta's `FILE` inserts as `BEGIN TRANSACTION; INSERT …; COMMIT` — the
   fixture seam. The old row-dict `apply_delta` + `_copy_rows` are gone.
- **`04` modernised `hasheset.py`**: standard PEP-8 4-space indent, f-strings, a
   public `HashSet.path` accessor, a `COLUMN_TYPES` map for the fixture DDL →
   `hasheset.py` is now **lint-clean** (was `W0212` + 2× `C0209`).
- **Left for `05`/`06`**: `dbhash` (NIST external binary) + `Provisioning manifest`
   + readiness gate. `Provenance.dataset()` still returns `set`/`release`/`deltas`;
   `dbhash` + the per-delta `dbhash` chain are a `06` addition.
- `lookup.py`/`app.py` **unchanged** — per-item `known/unknown/invalid` + `dataset`
   provenance already correct; the shape they assert (`set`/`release`/`deltas`) is
   unchanged by `03`/`04`. `dbhash` in the `dataset` block is a `06` addition.

## 4. Gotchas for next session

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

- Suite (in-container, == CI `test` job): **42 passed, 0 skipped, 98% coverage**,
   exit 0.
- Lint: **`hasheset.py` is 0 findings now** (the `04` modernisation cleared the prior
   `W0212` + 2× `C0209`). The remaining module findings are pre-existing and untouched:
   `app.py` C0303/W1405 (trailing whitespace / inconsistent quotes) and the `E0015`
   `pylintrc` quirk; overall pylint ≈ `9.3`/`10`.
- **Next: ticket `05`** — the **Provisioner** (3-layer integrity per ADR-0006): fetch →
    verify (SHA-1 `.zip_sha` sidecar → inner `signatures.txt` SHA-256 → NIST `dbhash`
    over the final post-delta db, matching `dbhashes.txt` `481e5f55…e52a`) → apply the
    ordered deltas via `apply_delta`/`executescript` → write the queryable Hash Set +
    Sidecar + **Provisioning manifest**. `dbhash` itself is **not installed** — a
    verified stand-in is needed (see ADR-0006). `06` (manifest + readiness gate +
    per-result `dbhash`) follows; `07 ∥ 08 ∥ 09` fork off `06`. Commit per tracer bullet.
