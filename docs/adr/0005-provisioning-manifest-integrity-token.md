# Provisioning manifest as the integrity token and readiness gate

Because the lookup interface is public, a **Lookup Result** is only trustworthy through the
**dataset** that answered it. But the service is a pure read-only consumer of a mounted
**Hash Set**: it cannot recompute NIST's integrity values at boot, and no manifest means an
unverified or stale volume could answer. So we make the **Provisioner**'s one-time attestation
— the **Provisioning manifest** (the **Set**, **Release**, ordered **Delta releases**, and the
three integrity values) — the thing the service checks at startup. The service is **ready** only
when the manifest is present **and** its integrity still matches the mounted **Hash Set**;
otherwise it reports not-ready and serves nothing. The **Provisioning manifest** records the
**dbhash** + **Release** (+ ordered Deltas) the volume was built from and is the check `verify_readiness`
runs at boot; a mismatch refuses the volume.

- **Status**: accepted
- **Considered Options**: recompute the full NIST integrity chain at boot (rejected: the
   Minimal set is ~18 GB and the `dbhash` is an external, order-dependent token — this would
   gate every start-up on a multi-gigabyte recomputation and would require bundling NIST's
   `dbhash` binary into the image, for a check that provisioning already performed);
   trust the mount blindly (rejected: an unverified or partially-applied-delta volume could
   then answer, defeating the forensic guarantee for an open interface); keep integrity
   out-of-band with no gate (rejected: an operator could mount an unverified set and the
   service would silently answer against it). We instead accept the manifest as the
   integrity token the service is allowed to check.
- **Consequences**: every **Lookup Result** carries `set`, `release`, ordered `deltas`, and
   the final **dbhash** (the minimal fields to re-verify against `dbhashes.txt`); the full
   triple (zip SHA-1, inner SHA-256 signatures) and the ordered per-delta `dbhash` chain live
   in the manifest / `/health`, not repeated per result; `/health` surfaces `ready` plus the
    dataset identity; the **Provisioning manifest** lives in the **writable**
     data dir, separate from the read-only mount of the **Hash Set** -- the
     per-Algorithm hash index lives *inside* the mounted `rds.db` itself, not
     beside it.
