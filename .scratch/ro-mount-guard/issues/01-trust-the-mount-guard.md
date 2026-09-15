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

**Status:** ready-for-agent

- [ ] The container **boot** entry loads the mounted **Hash Set** **read-only** and does
       **not** rebuild its **hash index** (the **Provisioner** and **Delta** apply, not
       boot).
- [ ] `make verify` (the re-check of an already-provisioned volume) likewise loads the
       mounted **Hash Set** **read-only** without an index rebuild.
- [x] The source fix (read-only load at the two read-the-mount entry points) is
        committed -- `0af05af` ("In-database hash index + streamed delta apply +
       trust-the-mount"); `boot` and `make verify` now load the mounted db
       read-only and do not rebuild the index.
- [ ] A **white-box guard** (OS-portable, in CI) forces the index-build entry to fail
        (`AssertionError` naming the invariant — "boot/verify must not rebuild the index")
       and asserts both **boot** and `verify` still succeed — so any re-introduction of a
       writable-connect / index-rebuild path is caught on every platform.
- [ ] A **read-only-volume guard** provisions an indexed volume, makes the data dir
        **read-only**, and asserts **boot** and `verify` still succeed on it — the faithful
       reproduction of the original tension (a writable `CREATE INDEX` would open a
       journal in the dir and fail). Run it POSIX-only; skip on Windows and when running as
       root, where a read-only *dir* does not force the failure.
- [ ] The deploy-smoke fixture carries the **hash index** it claims to ship (Provisioner
       parity), so a no-rebuild boot against a fixture stays faithful to what the Provisioner
       writes.

## Notes

- The read-only connection is the existing `HashSet` constructor's behaviour; the guard
  asserts that the boot / verify entry points *use it* rather than the writable
  `provision`/`build_hash_index` path.
- The white-box guard is the safe-everywhere regression check; the read-only-dir guard is
  the one that actually reproduces the original failure mode (SQLite opens a journal/wal in
  the containing dir on any write transaction), hence POSIX-only.
