# Handoff: nsrllookup — migration COMPLETE; rebase effort `rds-v3-live` DESIGNED, 0/7 coded

Two things to know: the **RDS V3 migration is complete and committed**, but it was
built against a **synthetic** on-disk schema. A follow-up effort, **`rds-v3-live`**,
re-bases the data layer onto NIST's **real** RDS V3 layout and makes the service
deployable. `rds-v3-live` is **fully designed and approved (grilled), but no ticket
on it is coded yet**. Nothing here is a dead end: the migration suite is green and the
rebase plan is locked. See the design at `.scratch/rds-v3-live/` (to be created as
ticket `01` lands) and `docs/adr/0005..0006` (to be written).

## 1. Migration status (unchanged, still true)

All tickets `04`–`14` in `.scratch/rds-v3-migration/issues/` are `resolved`.
Tickets `01`–`03` were implemented at `74cf77d` and **their issue files still read
`ready-for-agent`**; that bookkeeping discrepancy was closed by committing `b8c5a6c`
("Mark tickets 01-03 resolved (implemented at 74cf77d)"). Full trail on `main`:
`5274666` → `74cf77d` (01–03) → `e02258a` (04–07 + devcontainer) →
`2a5b904` (08–14) → `786e518` (handoff) → **`b8c5a6c` (01–03 bookkeeping, newest)**.

Service: queries a mounted RDS V3 Minimal **Hash Set** (no `nsrlsvr`), `POST /check`
+ `/health` with full per-Algorithm provenance, append-only **Audit Trail** per
**Lookup Session**, **Delta** at ingest, no retired component.

- Suite (in-container, == CI): **38 passed, 0 skipped, 98% coverage**, exit 0.
- Lint: pylint 9.01/10; sole E-finding `E0015` is a pre-existing `pylintrc` quirk.
- Run the suite exactly as CI:
      test:  docker run --rm -v "$PWD":/workspace -w /workspace/api nsrllookup-dev \
                python -m pytest --cov=. --cov-report=term-missing -q
      build: docker build -t nsrllookup-dev -f .devcontainer/Dockerfile .
      lint:  docker run --rm -v "$PWD":/workspace -w /workspace/api nsrllookup-dev \
                python -m pylint app.py lookup.py hasheset.py audit.py --rcfile=../pylintrc

## 2. WHY a rebase — the migration built on a synthetic schema

During the "make it live/deployable" pass, the team byte-probed **NIST's live primary
sources** (`s3.amazonaws.com/rds.nsrl.nist.gov/RDS/...`, `RDSv3_Docs/*.pdf`). The
on-disk layout ticket `04` "confirmed" is **NOT NIST's real one**:

- **Migration assumed** `METADATA(crc32, md5, md5sha1, sha1, sha256, filename)`,
  UPPERCASE digests, no index.
- **NIST's real Minimal set** is a `FILE(sha256, sha1, md5, crc32, file_name,
  file_size, package_id)` table (~432,866,777 rows / 72,015,285 distinct SHA-256)
  plus a `DISTINCT_HASH(sha256,sha1,md5,crc32)` **view**. There is **no `METADATA`
  table and no `md5sha1`**. `crc32` *is* present (matches our domain model), but
  `md5sha1`/`METADATA`/`filename` are invented. A real Hash Set therefore would not
  open against the current `hasheset.py`.
- **Deltas are NOT a database** — they are `.sql` files (`BEGIN TRANSACTION;
  INSERT/UPDATE/DELETE INTO FILE …`) applied with `sqlite3 … ; .read delta.sql`
  (Python `sqlite3.executescript` suffices; no CLI). Current `apply_delta()` takes
  Python row-dicts — fixture-shaped, must be reworked.
- **Integrity is 3 layers**: SHA-1 `.sha` sidecar on each zip; SHA-256 `signatures.txt`
  inside; NIST **`dbhash`** = the SQLite `dbhash` binary's 40-hex output over the
  final post-delta db, published per release in `dbhashes.txt`.
- **No cheap Minimal db exists**: the only complete real db under ~500 MiB is
  `RDS_2021.12.2_curated.zip` (86.9 MiB) — but that is the *curated* schema, not
  minimal. Minimal-layout byte-confirmation must come from the `schema.sql`/`signatures`
  NIST ships inside the ~206 MiB `RDS_*_modern_minimal_delta.zip`.

## 3. `rds-v3-live` — APPROVED DESIGN (0 of 7 tickets coded)

Grilled and agreed (every choice the recommended one). This is the live spec until
`.scratch/rds-v3-live/spec.md` is written by ticket `01`. It **supersedes ticket 04's
"confirmed layout" claim**.

**Data layer re-base**
- Real layout: `FILE(sha256,sha1,md5,crc32,file_name,file_size,package_id)` +
  `DISTINCT_HASH(sha256,sha1,md5,crc32)` view. Drop `md5sha1`; `file_name`≠`filename`;
  `crc32` present but a non-lookup column (keeps CONTEXT.md's "crc32 present, not a
  supported lookup").
- **Sidecar index**: persisted in the **writable** data dir (separate from the ro
  mount), built by **materialising `DISTINCT_HASH`** (~72M distinct digests,
  **UPPERCASED** — case-agnostic membership), not a raw 432M scan. Stores the **dbhash
  + release** it was built from; **refuses to serve on mismatch**, rebuilt on delta.
- **Deltas** applied as real `.sql` via `sqlite3.executescript` (the `.read`
  mechanism, no external CLI); rebuild sidecar + refresh provenance; fixtures model a
  delta as inserts.
- **Integrity (3 layers)**: SHA-1 sidecar, SHA-256 `signatures.txt`, NIST `dbhash`
  (**external `dbhash` binary** — accept as a provisioner-time dep; exact bit-level
  algo verified against NIST's `dbhashes.txt`, NOT re-implemented). The **container
  trusts the verified data dir** (no in-boot dbhash).

**Readiness gate + provenance surfacing**
- **Provisioning manifest** written by the provisioner into the writable data dir:
  `set` + `release` + ordered `deltas` + the 3 integrity values. Container at startup:
  `ready=true` **iff manifest present AND integrity matches** the mounted db.
- **Per-result `dataset`** carries `set`, `release`, `deltas` (ordered), **final
  `dbhash`** — enough to re-verify vs `dbhashes.txt`. Full triple + ordered **per-delta
  chain** (dbhash is order-dependent) lives in the manifest / `/health`.
- **Access**: public + audited, no auth (ADR-0004; auth toggle stays a later ticket).

**Provisioning (turnkey, out-of-band, never in build/CI)**
- Wizard-driven `make provision` / `make verify`: fetch → verify 3 layers → apply
  deltas in order → write `rds.db` + sidecar + manifest. Container stays a pure
  read-only consumer (no boot-time ingest; honours ADR-0003).
- **Real-data check, one-off, out of CI**: (a) byte-confirm the minimal `schema.sql`
  from NIST's shipped file; (b) **mechanics** smoke of reader+delta+dbhash on
  `RDS_2021.12.2_curated` (86.9 MiB — a different schema, so a *mechanics* proof only).
  Full ~18 GiB Minimal + deploy stay **operator steps**. **Deploy smoke this session**:
  build → run → `/health` + `/check` green, **fixture-based**.

**Domain model (single context ⇒ ROOT `CONTEXT.md`, glossary only, no impl):**
new/sharpen — real **Set schema** (`FILE`/`DISTINCT_HASH`, `crc32` a column),
**Sidecar index**, **Provisioner** + **Provisioning manifest** (integrity
attestation), **dbhash** (NIST dataset-hash = integrity token), sharpen **Delta
release** → "a `.sql` of INSERT/UPDATE/DELETE applied in order".
**ADR-0005** (manifest = integrity token / readiness gate) + **ADR-0006** (external
`dbhash` dependency / trust-the-mount).

**Ticket spine (`.scratch/rds-v3-live/issues/`, 9 tickets, all `ready-for-agent`):**
`01` byte-confirm the real `FILE`/`DISTINCT_HASH` schema from NIST `schema.sql` (frontier)
→ `02` domain model + ADR-0005/0006 (prefactor; `CONTEXT.md` + ADRs, split out of the old
 7-ticket 07) → `03` re-base data layer to `FILE`/`DISTINCT_HASH` + UPPERCASE/case-
 agnostic (a small wide refactor that lands green in one batch — not big enough to need
 expand–contract) → `04` `.sql` delta apply + rebuild sidecar → `05` Provisioner (3-layer
 integrity: SHA-1 sidecar, SHA-256 signatures, NIST `dbhash`; wizard-driven
  `make provision`/`verify`) → `06` provisioning manifest + readiness gate + per-result
 `dbhash` → fork: `07` real-data mechanics smoke (one-off on `RDS_2021.12.2_curated`, out of
  CI, ∥) `08` fixture deploy smoke (build → run → `/health`+`/check` green, the demoable
  terminal, ∥) `09` housekeeping (retire ticket 15, drop `live` marker, refresh README).
Linear `01→…→06`, forking `07 ∥ 08 ∥ 09` off `06`.

**Housekeeping (DONE in this pass; ready to commit alongside the effort)**
- **`live`-marker prune** done: `api/conftest.py` (removed `NSRLLOOKUP_LIVE` + `--live` +
   the `collection_modifyitems` skip hook) + `api/pytest.ini` (removed the `live` marker).
   Independent, harmless; committed as its own commit.
- **`ticket 15` retired** (`.scratch/rds-v3-migration/issues/15-provision-production-set.md`):
   `Status` flipped to `superseded by rds-v3-live` with a pointer; its "provision a
   production set" goal is now `rds-v3-live` tickets 05–08.
- Untracked agent tooling (never commit): `.agents/`, `.claude/`, `skills-lock.json`;
   `coverage.xml`/`.coverage` are gitignored build artifacts.

## 4. Gotchas for next session
- **Git has NO committed `user.*` config.** Commit with env vars
  (`GIT_AUTHOR_NAME=cybagard`, `GIT_AUTHOR_EMAIL=67512030+cybagard@users.noreply.github.com`,
  and `GIT_COMMITTER_*` the same). `git -c user.name=… -m …` **fails** (-c and -m
  cannot combine). **Commit cadence chosen: one commit per completed tracer bullet.**
- **Indentation quirk (recurring):** 4-space bodies; a docstring opener whose indent ≠
  the body's raises `IndentationError`. Keep docstring-opener indent == body indent, or
  write via the builder-pattern Python script then `ast.parse`.
- **No cheap Minimal db:** do NOT try to smoke the real minimal layout against
  `2021.12.2_curated` (different schema) or the 10.3 GiB demo zip — byte-confirm the
  minimal `schema.sql` from NIST's shipped artifacts and keep mechanics on `curated`.
- **NIST S3 facts (live, 2026-09-03):** bucket = `s3.amazonaws.com/rds.nsrl.nist.gov/RDS/`
  (NOT nist.gov — that host's download URL 403s). Bucket **listing is AccessDenied**
  (403) but individual objects are **public-read** (GET/range = 206): probe by exact
  name, don't directory-walk. Current release `2026.09.1` (delta-only; last full `2026.03.1`).
  Real objects: `RDS_2026.03.1_modern_minimal.zip` (~18 GiB),
  `RDS_2026.03.1_modern_minimal_delta.zip` (~206 MiB, contains `schema.sql` +
  `signatures.txt` + `…_delta.sql` + `readme.txt`), `RDS_2021.12.2_curated.zip`
  (86.9 MiB, a *curated* db). Each zip has `…_sha` (SHA-1 of the zip). Per-release
  `version.txt`/`dbhashes.txt`/`hash_counts.txt`/`README.txt` are live.

## 5. Suggested next step
The `rds-v3-live` spec + 9 tickets are written and committed. Start **ticket `01`** (the
only unblocked frontier): byte-confirm the minimal `FILE`/`DISTINCT_HASH` schema from NIST's
shipped `schema.sql`, then proceed `02 → 03 → … → 09` in dependency order (commit per
tracer bullet). `07 ∥ 08 ∥ 09` fork off `06`.
