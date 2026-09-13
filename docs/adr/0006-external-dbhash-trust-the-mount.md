# Accept NIST's external `dbhash` dependency; trust the verified mount

NIST's dataset-integrity token, **`dbhash`**, is the output of NIST's own `dbhash` binary over
the final post-delta database, published per **Release** in `dbhashes.txt`. Its bit-level
algorithm is not public, so we cannot re-derive it. We therefore accept `dbhash` as a
**provisioning-time external dependency**: the **Provisioner** reads NIST's published
`dbhash` from that **Release**'s `dbhashes.txt` and **records** it as the dataset Integrity
token in the **Provisioning manifest** — it *attests* the token, not recompute it — and the
service **trusts** the resulting verified data dir; it does **not** recompute `dbhash` at
boot. Integrity is established once, at provisioning, and asserted by the **Provisioning
manifest** (ADR-0005).

- **Status**: accepted
- **Considered Options**: re-implement `dbhash` in-repo (rejected: its bit-level algorithm is
   not public, so any re-implementation could match a subset and diverge from NIST in a way
   forensics cannot tolerate, and it couples us to an opaque algorithm); ship NIST's `dbhash`
   binary in the service image and recompute at boot (rejected: it bloats and complicates the
   container and turns a one-time attestation into a per-start-up, multi-gigabyte operation,
   against ADR-0003's "never at build/CI/boot" principle and ADR-0001's read-only consumer);
   skip layer 3 and trust transport-level integrity only (rejected: zip SHA-1 and inner
   SHA-256 do not prove the *applied* database equals what NIST published). We accept `dbhash`
   as an out-of-band, provisioning-time dependency and trust the verified mount.
- **Consequences**: the **Provisioner** (ticket 05) is the only component that depends on the
   `dbhash` binary, and only off the critical path; the **dbhashes.txt** value for the
   provisioned **Release** is recorded in the **Provisioning manifest**; the container image
   stays free of `dbhash` and of any boot-time integrity recomputation; if NIST ever publishes
   the algorithm, the gate can be recomputed in-image, but that is not the current design.
