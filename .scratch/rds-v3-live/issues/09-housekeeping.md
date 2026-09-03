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

**Status:** ready-for-agent

- [ ] `rds-v3-migration` ticket 15 is flipped to **superseded by `rds-v3-live`** with a
        pointer to this effort (its goal is now tickets 05–08), left as history only.
- [ ] The dormant `live` marker (`--live` / `NSRLLOOKUP_LIVE` / pytest `live` marker) is
        removed with no test depending on it.
- [ ] `README.md` reflects the real layout, the readiness gate, and the fixture deploy path.
- [ ] The suite stays green after the prune (the marker was unused).
