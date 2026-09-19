# 01: Guard the "trust the mount" invariant

**What to build:** a regression guard that proves the ADR-0006 "trust the mount, don't
recompute" invariant: a booted or re-checked volume must open the mounted **Hash Set**
**read-only** and must **never rebuild its per-Algorithm **hash index** at boot time.
Today nothing enforces this — the deploy smoke provisions into a writable temp dir and
never asserts the negative, so a writable-connect path (an old-style index rebuild) could
creep back in and the suite would stay green. This ticket lands the invariant **together
with the source fix** so the slice is atomic: the guard fails without the fix, and the
suite is green only because the fix is present.

The fix makes the two **read-the-mount** entry points — container **boot** and the
`make verify` re-check — load the mounted **Hash Set** read-only (a single read-only
connection, no index rebuild), leaving the **Provisioner** and **Delta** apply as the
only writable paths (they build the in-db **hash index**). The ADR-0006 principle: the
service is a pure read-only consumer of the verified data dir; integrity is established
once, at provisioning.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] The container **boot** entry loads the mounted **Hash Set** **read-only** and does
        **not** rebuild its **hash index** (the **Provisioner** and **Delta** apply, not
        boot).
- [x] `make verify` (the re-check of an already-provisioned volume) likewise loads the
        mounted **Hash Set** **read-only** without an index rebuild.
- [x] The source fix (read-only load at the two read-the-mount entry points) is
         committed -- `0af05af` ("In-database hash index + streamed delta apply +
        trust-the-mount"); `boot` and `make verify` now load the mounted db
        read-only and do not rebuild the index.
- [x] A **white-box guard** (OS-portable, in CI) forces the index-build entry to fail
        (`AssertionError` naming the invariant — "boot/verify must not rebuild the index")
        and asserts both **boot** and `verify` still succeed — so any re-introduction of a
        writable-connect / index-rebuild path is caught on every platform.
- [x] A **read-only-volume guard** provisions an indexed volume, makes the data dir
        **read-only**, and asserts **boot** and `verify` still succeed on it — the faithful
        reproduction of the original tension (a writable `CREATE INDEX` would open a
        journal in the dir and fail). Run it POSIX-only; skip on Windows and when running as
        root, where a read-only *dir* does not force the failure.
- [x] The deploy-smoke fixture carries the **hash index** it claims to ship (Provisioner
        parity), so a no-rebuild boot against a fixture stays faithful to what the
        Provisioner writes.

## Notes

- The read-only connection is the existing `HashSet` constructor's behaviour; the guard
  asserts that the boot / verify entry points *use it* rather than the writable
  `provision`/`build_hash_index` path.
- The white-box guard is the safe-everywhere regression check; the read-only-dir guard is
  the one that actually reproduces the original failure mode (SQLite opens a journal/wal in
  the containing dir on any write transaction), hence POSIX-only.

## Answer

The ADR-0006 "trust the mount" invariant is now guarded by two regression tests in
`api/tests/integration/test_trust_the_mount.py`, both driven off a fixture volume the
test provisions exactly as the Provisioner would (real-layout `rds.db` +
`hasheset.build_hash_index` + Provisioning manifest — the same shape
`test_deploy_smoke` ships).

**White-box guard (OS-portable, in CI).**
`test_boot_and_verify_never_rebuild_index` forces the index-build entries —
`hasheset.build_hash_index`, `hasheset.provision`, and `hasheset._rebuild_index` — to
fail with `AssertionError("boot/verify must not rebuild the index")`, then drives
container boot (`boot.bootstrap`) and the `make verify` re-check
(`driver.verify_release`) and asserts both still end `ready` (`/health` ready,
`well_formed` + `ready` checks). Any re-introduction of a writable-connect /
index-rebuild path at a read-the-mount entry point trips the stub and fails the suite on
every platform.

**Read-only-volume guard (POSIX-only).**
`test_read_only_volume_still_boots_and_verifies` provisions the indexed volume, makes the
data dir read-only (`0o555`), and asserts boot and `verify` still succeed on it — a
membership lookup is answered over the read-only mount and both entry points end ready.
It skips on Windows and as root, where a read-only *dir* does not force the failure; the
skip is a single computed reason string used as the marker's `reason`, with a boolean
condition (a string *condition* would make pytest `eval` it).

**Proven both guards fail without the fix.** Restoring the pre-`0af05af`
`hasheset.provision(db_path, …)` calls in `bootstrap` / `verify_release` turns the
white-box guard red with the invariant's `AssertionError`; and a writable index build
against a raw (unindexed) volume on a read-only dir fails with
`OperationalError: attempt to write a readonly database` — the original tension, since a
provisioned volume already carries its index and `CREATE INDEX IF NOT EXISTS` is a
no-op write only when the index would actually be built.

**Fixture parity.** The deploy-smoke fixture already carries the hash index it claims to
ship (`hasheset.build_hash_index` in `test_deploy_smoke._provision_volume`, landed with
the `0af05af` source fix), so a no-rebuild boot against the fixture stays faithful to
what the Provisioner writes.

**CI.** `.github/workflows/test.yml` carried an indentation bug that made the whole file
unparseable YAML (the coverage step was nested under the install step's `run:` key, so
GitHub refused the workflow and the suite never ran in CI). The step is now a proper
top-level step; the file parses to four steps.
