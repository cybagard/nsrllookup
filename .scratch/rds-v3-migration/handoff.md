# Handoff: nsrllookup RDS V3 migration — checkpoint after tickets 04–07 (MD5 tracer bullet)

**Session focus next up:** implement tickets 08–14 of `.scratch/rds-v3-migration/issues/`
(08 widen SHA-1 & SHA-256 / 09 audit entries / 10 apply-delta / 11 rebuild-index + refresh
/health / 12 log request-level rejections / 13 retire-nsrlsvr / 14 end-to-end).

## State of the world
- Repo `/Users/promptcritical/nsrllookup`, branch `main`.
- `74cf77d` (prior session) = modern stack + pytest migration + CI test job.
- **This session added the first complete end-to-end tracer bullet (tickets 04–07):**
    - `api/hasheset.py` — added `Provenance` (Set / Release / applied Deltas), `HashSet`
      (per-**Algorithm** `hash→known` index built once at ingest via `provision()`, not per
      request; `is_known(algorithm, digest)`), on top of the existing schema constants +
      `build_minimal_fixture_db`.
    - `api/lookup.py` — **new Seam 2**: `look_up(hash_set, digests, algorithm) ->
      [Lookup Result]` + `is_well_formed`; separates **Invalid** (not well-formed for the
      declared **Algorithm**) from **Unknown** (checked, absent); each result carries the
      full `dataset` provenance per the spec's API contract.
    - `api/app.py` — **Seam 1**: `POST /check` (one **Algorithm** + one-or-more **Digests**,
      delegates to `lookup.look_up`) and `/health` (`ready` + `dataset`); `configure()`
      installs the provisioned **Hash Set** (not-provisioned → `/health` not-ready,
      `/check` 503). Unsupported **Algorithm** / malformed body → request-level 4xx with no
      `results`. The retired MD5-only `GET /check/<hash>` is kept behind an on-demand
      `nsrllookup` import (deleted in ticket 13) so `from app import api` stays boot-safe.
    - Tests: `api/tests/unit/test_lookup.py` (Seam 2) and
      `api/tests/integration/test_check_health.py` (Seam 1).

## What is NOT done yet (next tickets)
- **08**: index + `look_up` + `POST /check` already accept SHA-1 & SHA-256 in code; add the
  per-**Algorithm**-knownness and SHA-256-dedup assertions.
- **09**: an **Audit Entry** for every **Lookup Session** (durable, append-only **Audit
  Trail**), asserted black-box at Seam 1.
- **10/11**: apply a **Delta** at ingest; rebuild index + refresh `/health` provenance.
- **12**: request-level rejections also become **Audit Entries**.
- **13**: delete `nsrllookup.py`, the legacy `GET /check/<hash>`, the two-service
  compose/README flow; single-service + mounted-volume only.
- **14**: end-to-end verification.

## Two test seams (TDD only at these — from the spec)
- **Seam 1 = the API boundary.** `POST /check` + `/health` via Flask `test_client()`;
  per-item known/unknown/invalid, 200-with-per-item-`invalid` vs 4xx-on-bad-algorithm/malformed-
  body, full provenance in `dataset`, and (ticket 09) that a session produced an **Audit
  Entry** (black-boxed through this seam).
- **Seam 2 = the lookup module.** `look_up(hash_set, digests, algorithm) -> [Lookup Result]`
  against a fixture **Hash Set**. Used for MD5/SHA-1/SHA-256 equivalence + SHA-256 dedup.
- Provision / delta-apply / index-build have **no unit test** — only a build-time smoke
  check.

## Execution environment (NEW this session)
- A **devcontainer** was built: `.devcontainer/Dockerfile` (python:3.14-slim, `pip install -r
  api/requirements.txt` + `pylint`) + `.devcontainer/devcontainer.json` (context `..`,
  workspace `/workspace`). Only `docker` is present (no `devcontainer` CLI), so build/run via:
     - build: `docker build -t nsrllookup-dev -f .devcontainer/Dockerfile .`
     - test:  `docker run --rm -v "$PWD":/workspace -w /workspace/api nsrllookup-dev \
                python -m pytest --cov=. --cov-report=term-missing -q`
     - lint:  `docker run --rm -v "$PWD":/workspace -w /workspace/api nsrllookup-dev \
                python -m pylint app.py lookup.py hasheset.py --rcfile=../pylintrc`
  Host `.venv/` still works too; the container is the preferred, reproducible runner.

## Current suite (green, in-container and on-host)
- `20 passed, 6 skipped`. The 6 skips are the legacy live-server tests in
  `tests/integration/test_hash_lookup.py` (gated behind `--live`/`NSRLLOOKUP_LIVE`).
- Coverage: totals ~73%; `nsrllookup.py` (retired, ticket 13) is the only 0% file.

## Gotchas
- **Indentation quirk:** the existing source uses 4-space bodies with a 5-space docstring
  opener (tolerated by Python only when the docstring indent equals what follows). New
  functions that mix 4/5 spaces raise `IndentationError`. Normalize new bodies to a fixed
  indent; the safe recipe was to force standalone `"""…"""` opener lines to the body indent.
- `nsrllookup.py` stays until ticket 13; nothing new imports it except the retained
  `GET /check/<hash>` behind an on-demand import.
- `api/app.py` keeps the `NSRLLookup` import on-demand so `from app import api` is
  boot-safe — preserve that when wiring 09/12.
- Git has NO committed `user.*` config. Commit with env vars:
  `GIT_AUTHOR_NAME=cybagard GIT_AUTHOR_EMAIL=67512030+cybagard@users.noreply.github.com
   GIT_COMMITTER_NAME=cybagard GIT_COMMITTER_EMAIL=<same> git commit -m "..."`
  (`git -c user.name=... -c user.email=... -m` FAILS — `-c` and `-m` can't combine.)
- Per the project's cadence, after each todo write a handoff and pause for confirmation.

## Suggested skills
- `implement` (driver), `tdd` (red→green at the two seams), `code-review` (per slice + end),
  `handoff` (after each todo), `codebase-design` (vocabulary for the index / audit trail).
