# 08: Fixture deploy smoke (end-to-end)

**What to build:** the demoable terminal slice — a fixture-based **deploy smoke** that proves
the deploy path this session without a multi-gigabyte download: **build the image → run it
→ `/health` reports `ready` and `/check` returns a `known`** against a fixture **Hash Set**,
with `dbhash` in the `dataset` block. A full ~18 GiB real deployment stays an operator step,
out of this ticket.

**Blocked by:** 06 (manifest/readiness + per-result `dbhash`) — the smoke asserts `ready` +
a `known` answer carrying `dbhash`, which exist only after 06.

**Status:** resolved

- [x] Build → run the image → `/health` reports `ready` and `/check` returns a `known`
         (with `dbhash` in the `dataset` block), on a fixture **Hash Set**.
- [x] The smoke stays green on fixtures with **no live server and no real-data download**
         (a real **Hash Set** is not required to run it).

## Answer

The deploy path is now the one the container actually runs, and a fixture
smoke proves it end-to-end. Two things landed:

**A boot seam (`api/boot.py`).** The container's `__main__` previously called
`serve()` with no Hash Set loaded, so a running image could never report
`ready` — it always came up `not-ready`. `bootstrap()` is the one place a
provisioned, verified volume becomes a ready app: it reads the **Provisioning
manifest** and the queryable `rds.db` from the mounted data dir, rebuilds the
**Sidecar index** via `hasheset.provision`, and `app.configure`s the loaded
**Hash Set** + manifest. A missing db or manifest leaves the app unconfigured,
so the readiness gate (ADR-0005) holds an unverified volume to `not-ready`.
`__main__` now does `bootstrap()` then `serve(_app.api, …)`; it serves the
`app` *module's* `api`, not `__main__`'s, so the served server is the one
`bootstrap` configured (the smoke caught this — a bare `serve(api, …)` served a
server that never saw the Hash Set).

**Fixture deploy smoke (`tests/integration/test_deploy_smoke.py`).** The
demoable slice: a fixture **Hash Set** + its **Provisioning manifest** are
written to a temp data dir exactly as the Provisioner would (the same call
the real provisioner makes: `build_minimal_fixture_db` + `write_manifest`),
then the service is booted through `bootstrap` and driven through Flask's test
client. `test_boot_report_ready_and_known_with_dbhash` asserts `/health` is
`ready` with the `dbhash`-bearing `dataset` and `/check` returns `known`
carrying the same `dataset`; `test_boot_without_volume_is_not_ready` proves the
empty-volume control — `not-ready` and `/check` 503. No live server and no
real-data download: the smoke is fixture-only, and a real **Hash Set** is not
required to run it.

**Compose.** `docker-compose.prod.yml` and `docker-compose.build.yml` now mount
the whole data dir (`./data:/data:ro`) instead of the single `rds.db` file, so
the **Provisioning manifest** next to the db is visible to `boot`; the Audit
Trail mount is unchanged. Both validate under `docker compose config`.

**Demonstration (out of CI).** A real container run — the dev image, the same
app code + deps — booted against a fixture volume and answered over HTTP:
`/health` `→{"ready":true,"dataset":{…,"dbhash":"deadbeef"}}`;
`/check` md5 `→{"status":"known","dataset":{…,"dbhash":"deadbeef"}}` and an
absent digest `→{"status":"unknown"}`; the no-volume control `→{"ready":false}`;
and the Audit Trail recorded both sessions.

Suite: **60 passed, 98%+ coverage**; `boot.py` at 100% and `pylint` clean
(10/10, the `E0015`/`UserWarning` lines being the pre-existing `pylintrc`
quirks). The full ~18 GiB Minimal **Set** and the production deploy stay
operator steps, out of this ticket.
