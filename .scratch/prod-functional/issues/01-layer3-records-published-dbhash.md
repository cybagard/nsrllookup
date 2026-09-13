# 01: Layer 3 integrity records NIST's published dbhash

**What to build:** the **Provisioner**'s third integrity layer stops using a stand-in
token and instead *records* NIST's published **`dbhash`** for the **Release** — the value
NIST ships in that release's `dbhashes.txt` — into the **Provisioning manifest**. This is
the slice that makes the dataset's Integrity token *real*: a forensic consumer can re-verify
any **Lookup Result** against NIST's published token because the recorded token is NIST's,
not a locally-computed stand-in. Respects ADR-0006 (the `dbhash` algorithm is not public, so
the token is *recorded*, not recomputed) and ADR-0005 (the **Provisioning manifest** stays the
integrity token the service checks at boot; the service still trusts the verified mount).

The existing layers 1 (zip **SHA-1** vs sidecar) and 2 (inner **SHA-256** vs
`signatures.txt`) stay unchanged. The compute-and-compare layer-3 check is kept *beside* the
new record-and-attest path so the fixture suite does not break (expand, do not break); the
turnkey path uses record-and-attest. This slice also updates the ADR-0006 consequence text:
the Provisioner *records* NIST's published `dbhash`, not "runs NIST's `dbhash`" — the accepted
decision (external dependency, trust the verified mount, no boot-time recompute) is unchanged.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [ ] Layer 3 reads NIST's published `dbhash` for the **Release** (from that release's
        `dbhashes.txt`) and records it as the dataset Integrity token in the **Provisioning
        manifest**, rather than computing a local stand-in.
- [ ] The compute-and-compare layer-3 check remains available for the fixture suite; the new
        record-and-attest path coexists without breaking existing tests.
- [ ] Layers 1 (zip **SHA-1**) and 2 (inner **SHA-256**) are untouched.
- [ ] A fixture test proves layer 3 accepts a published token / refuses a mismatch and that the
        recorded token round-trips through the manifest.
- [ ] The existing suite (API + lookup seams) stays green; ADR-0006 is refined to "records the
        published token".
