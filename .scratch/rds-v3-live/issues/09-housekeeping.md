# 09: Housekeeping — retire superseded ticket 15, drop the dormant live marker, update docs

**What to build:** the non-code cleanup that this effort displaces. **Retire
`rds-v3-migration` ticket 15** ("Provision a production RDS V3 Minimal Set") as
**superseded** by this effort — its goal is carried forward as `rds-v3-live` tickets
05–08. **Drop the dormant `live` marker** the migration left behind (the `--live` opt-in +
`NSRLLOOKUP_LIVE` env gate + the `live` pytest marker; no test uses it after the legacy
live test was deleted in migration ticket 13) — an independent, harmless prune. **Update
`README.md`** to reflect the real `FILE`/`DISTINCT_HASH` layout, the readiness gate, and
the fixture deploy path.

**Blocked by:** 06 (manifest/readiness) — the README reflects the readiness gate and the
smoke path that exist only after 06; ticket 15 is retired once the work it anticipated is
on this spine.

**Status:** resolved

- [x] `rds-v3-migration` ticket 15 is flipped to **superseded by `rds-v3-live`** with a
        pointer to this effort (its goal is now tickets 05–08), left as history only.
- [x] The dormant `live` marker (`--live` / `NSRLLOOKUP_LIVE` / pytest `live` marker) is
        removed with no test depending on it.
- [x] `README.md` reflects the real layout, the readiness gate, and the fixture deploy path.
- [x] The suite stays green after the prune (the marker was unused).

## Resolution

- **Ticket 15 retired:** `…/rds-v3-migration/issues/15-provision-production-set.md`
   already carried a `**Status:** superseded by `rds-v3-live`` banner noting the goal
   moved to tickets 04–08 (now 05–08 on the spine); left as history only, no re-litigation.
- **Dormant `live` marker:** the `--live` opt-in + `NSRLLOOKUP_LIVE` gate + the pytest
   `live` marker were already pruned in `d01b933` ("Prune the dormant live marker"); this
   pass removed the last stray reference — the stale `# Live-server tests are gated…`
   comment in `.github/workflows/test.yml` — so no code or config mentions the marker
   and no test depends on it.
- **README:** re-pointed at the real `FILE`/`DISTINCT_HASH` **Set schema**, the
   **Provisioner** / three-layer integrity, the **Provisioning manifest** **readiness
   gate**, the **dbhash**-bearing `dataset` block, and the fixture **deploy smoke**
   (`test_deploy_smoke.py`); ADR range widened to `0001..0006` and the spec pointer to
   `rds-v3-live/spec.md`.
